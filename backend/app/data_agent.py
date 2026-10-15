"""Run real data/representation tool calls, choosing the next call from results."""

import json
import time

from app.chat_cancellation import check_cancelled
from app.agent_plan import BudgetExceeded, MAX_REPLANS, PlanError, SAFETY_STEPS, choose_data_action
from app.data_plan import DataPlanError, MAX_QUERIES, MAX_WIDGETS, generate_sql, select_widgets
from app.query import QueryError, execute_readonly


def _view(query):
    return {key: query[key] for key in ("query_id", "sql", "title", "purpose", "status",
        "columns", "row_count", "row_limit", "repairs") if key in query}


def _signature(widget):
    return (widget["component"], json.dumps(widget["props"].get("column_map", {}), sort_keys=True))


def run_data_agent(message, *, schema, full_schema, history, references, context, deadline,
                   db_url, allowed_tables, create_widget, execution_state, original_request=None):
    queries, specs, created, actions = {}, {}, {}, []
    serial, version, decisions, repairs, feedback = 0, 0, 0, 0, None
    seen = {}
    summary, stop, stop_reason = "요청한 조회 결과를 준비했습니다.", "done", None
    model = {}
    try:
        while True:
            check_cancelled()
            if time.monotonic() >= deadline:
                raise BudgetExceeded("실행 시간 또는 작업 호출 한도에 도달했습니다.")
            state = {"queries": [_view(query) for query in queries.values()],
                "widgets": [{"widget_id": wid, "query_id": spec["query_id"], "component": spec["component"],
                    "title": spec["title"], "column_map": spec["props"].get("column_map", {}),
                    "status": "created" if wid in created else spec["status"]} for wid, spec in specs.items()],
                "tool_history": actions, "feedback": feedback,
                "remaining_calls": SAFETY_STEPS - execution_state["calls"]}
            decisions += 1
            choice = choose_data_action(message, state, history, context, deadline, original_request=original_request)
            action = choice["action"]
            if action in ("finish", "incomplete"):
                represented = {specs[wid]["query_id"] for wid in created}
                complete = bool(queries and created) and all(q["status"] == "executed" for q in queries.values()) \
                    and all(wid in created for wid in specs) and represented == set(queries)
                if action == "finish" and not complete:
                    feedback = "미실행 SQL·미생성 위젯이 있거나 생성 결과가 없습니다. 필요한 작업을 계속하세요."
                    key = ("finish", version)
                    seen[key] = seen.get(key, 0) + 1
                    if seen[key] < 2:
                        continue
                    stop, stop_reason = "no_progress", feedback
                elif action == "incomplete":
                    stop, stop_reason = "incomplete", choice["reason"] or "계속할 유효한 작업을 정하지 못했습니다."
                actions.append({"action": "evaluate", "status": "ok" if stop == "done" else "incomplete",
                                "verdict": "done" if stop == "done" else "incomplete",
                                "reason": choice["reason"] or stop_reason or "조회와 표현 목표 충족"})
                break
            fingerprint = (action, choice.get("query_id"), choice.get("widget_id"), choice["request"], version)
            if execution_state["calls"] >= SAFETY_STEPS:
                raise BudgetExceeded("작업 호출 한도에 도달했습니다.")
            seen[fingerprint] = seen.get(fingerprint, 0) + 1
            if seen[fingerprint] > 2:
                stop, stop_reason = "no_progress", "같은 호출이 결과를 바꾸지 못하고 반복됐습니다."
                break
            execution_state["calls"] += 1
            trace = {"action": action, "call": execution_state["calls"], "status": "ok", "reason": choice["reason"]}
            for key in ("query_id", "widget_id"):
                if key in choice:
                    trace[key] = choice[key]
            actions.append(trace)
            try:
                if action == "generate_sql":
                    replacing = choice.get("query_id")
                    if replacing and replacing not in queries:
                        raise DataPlanError("수정할 조회 ID가 없습니다.")
                    if replacing and repairs >= MAX_REPLANS:
                        raise DataPlanError("SQL 수정 횟수 한도에 도달했습니다.")
                    data, model = generate_sql(choice["request"], schema=full_schema if replacing else schema,
                        history=history, references=references, context=context, deadline=deadline,
                        original_request=original_request or message,
                        repair_hint={"previous_query": _view(queries[replacing]), "feedback": feedback} if replacing else None)
                    if replacing and len(data["queries"]) != 1:
                        raise DataPlanError("기존 조회 수정은 같은 ID의 SQL 하나를 반환해야 합니다.")
                    if not replacing and len(queries) + len(data["queries"]) > MAX_QUERIES:
                        raise DataPlanError("조회 개수 한도를 초과했습니다.")
                    sqls = [item["sql"].rstrip(";").strip() for item in data["queries"]]
                    existing_sqls = {item["sql"].rstrip(";").strip() for item in queries.values()}
                    if len(set(sqls)) != len(sqls) or any(sql in existing_sqls for sql in sqls):
                        raise DataPlanError("동일 SQL을 다시 생성하지 말고 기존 조회를 사용하세요.")
                    ids = []
                    for item in data["queries"]:
                        qid = replacing or f"query_{len(queries) + 1}"
                        queries[qid] = {**item, "query_id": qid, "status": "generated", "repairs": repairs + 1 if replacing else 0}
                        ids.append(qid)
                    if replacing:
                        repairs += 1
                        for wid in [wid for wid, spec in specs.items() if spec["query_id"] == replacing]:
                            specs.pop(wid)
                            created.pop(wid, None)
                    summary = data["summary"]
                    trace.update(count=len(ids), query_ids=ids, repaired=bool(replacing))
                elif action == "execute_sql":
                    qid = choice.get("query_id")
                    if qid not in queries or queries[qid]["status"] == "executed":
                        raise DataPlanError("실행 가능한 미완료 조회 ID가 필요합니다.")
                    query = queries[qid]
                    metadata = {}
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise BudgetExceeded("실행 시간 한도에 도달했습니다.")
                    rows = execute_readonly(db_url, query["sql"], allowed_tables=allowed_tables,
                        timeout_seconds=min(10, max(1, int(remaining))), result_metadata=metadata)
                    names = [column["name"] for column in metadata["columns"]]
                    if len(set(names)) != len(names):
                        raise DataPlanError("조회 컬럼 이름이 중복됩니다. 구별되는 SQL 별칭으로 수정하세요.")
                    query.update(metadata, rows=rows, status="executed")
                    trace.update(count=1, row_count=len(rows), columns=[c["name"] for c in metadata["columns"]])
                elif action == "select_widgets":
                    qid = choice.get("query_id")
                    if qid not in queries or queries[qid]["status"] != "executed":
                        raise DataPlanError("SQL 실행 완료 후에만 위젯을 선택할 수 있습니다.")
                    existing = [spec for wid, spec in specs.items() if spec["query_id"] == qid and wid in created]
                    selected, model = select_widgets(choice["request"], result=_view(queries[qid]), history=history,
                        context=context, deadline=deadline, original_request=original_request or message,
                        existing_widgets=[{"component": spec["component"], "title": spec["title"], "props": spec["props"]} for spec in existing],
                        feedback=feedback)
                    signatures = {_signature(spec) for spec in existing}
                    fresh = []
                    for widget in selected:
                        signature = _signature(widget)
                        if signature not in signatures:
                            fresh.append(widget)
                            signatures.add(signature)
                    if not fresh:
                        raise DataPlanError("같은 위젯을 다시 선택하지 말고 필요한 다른 표현을 선택하세요.")
                    pending_ids = [wid for wid, spec in specs.items() if spec["query_id"] == qid and wid not in created]
                    if len(specs) - len(pending_ids) + len(fresh) > MAX_WIDGETS:
                        raise DataPlanError("위젯 개수 한도를 초과했습니다.")
                    for wid in pending_ids:
                        specs.pop(wid)
                    ids = []
                    for widget in fresh:
                        serial += 1
                        wid = f"widget_{serial}"
                        specs[wid] = {**widget, "query_id": qid, "status": "selected"}
                        ids.append(wid)
                    trace.update(count=len(ids), widget_ids=ids, components=[w["component"] for w in fresh])
                elif action == "create_widget":
                    wid = choice.get("widget_id")
                    if wid not in specs or wid in created:
                        raise DataPlanError("생성 가능한 미완료 위젯 ID가 필요합니다.")
                    spec = specs[wid]
                    result = queries[spec["query_id"]]
                    trace.update(query_id=spec["query_id"], component=spec["component"], title=spec["title"])
                    created[wid] = create_widget(spec, result)
                    spec["status"] = "created"
                    trace.update(count=1)
                version += 1
                feedback = None
            except BudgetExceeded:
                trace.update(status="incomplete", reason="실행 시간 한도에 도달했습니다.")
                raise
            except Exception as exc:
                # Keep raw database/model diagnostics out of state, prompts and saved trace.
                trace.update(status="error", reason=f"{action} 호출에 실패했습니다.")
                feedback = str(exc) if isinstance(exc, (DataPlanError, QueryError, ValueError)) else trace["reason"]
                if action == "execute_sql" and choice.get("query_id") in queries:
                    queries[choice["query_id"]]["status"] = "failed"
                if action == "create_widget" and choice.get("widget_id") in specs:
                    specs[choice["widget_id"]]["status"] = "failed"
    except BudgetExceeded:
        stop, stop_reason = "budget", "실행 시간 또는 작업 호출 한도에 도달했습니다."
    except PlanError:
        stop, stop_reason = "incomplete", "다음 작업 또는 완료 여부를 판단하지 못했습니다."

    widgets = list(created.values())
    if stop != "done":
        summary = "완료된 일부 위젯을 반환합니다." if widgets else ""
    metadata = {**model, "actions": actions, "decision_calls": decisions, "data_stop": stop, "data_stop_reason": stop_reason,
        "sql_generation": {"count": len(queries), "repaired": bool(repairs), "repairs": repairs},
        "widget_selection": {"count": len(specs), "components": [spec["component"] for spec in specs.values()]},
        "widget_creation": {"count": len(widgets)}, "result_evidence": [_view(q) for q in queries.values() if q["status"] == "executed"]}
    prepared = {q["sql"]: q["rows"] for q in queries.values() if q["status"] == "executed"}
    return {"summary": summary, "artifact_type": "dashboard" if len(widgets) > 1 else "widget", "widgets": widgets}, metadata, prepared
