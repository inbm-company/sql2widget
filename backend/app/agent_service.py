"""Orchestrate live LLM planning, SQL execution, and fixed SOC demo sources."""

from __future__ import annotations

import secrets
import time
from typing import Any

from app.agent import sanitize_artifact
from app.agent_plan import (BudgetExceeded, LOOP_SECONDS, PlanError,
                            SAFETY_STEPS, evaluate, make_plan, model_context, single_step_plan)
from app import question_similarity, schema_linking
from app.chat_flow import conversation_flow
from app.config import ALLOWED_COMPONENTS, DEMO_CUSTOMER_DATABASE_URL
from app.documents import build_solution_from_sources, get_document_provider
from app.data_plan import DataPlanError, generate_sql, select_widgets
from app.intent_router import RouteError, choices_for, decide_route
from app.llm import effective_provider, json_with_llm
from app.prompts import GENERAL_CHAT_HINT, SCHEMA_QA_HINT
from app.query import QueryError, execute_readonly
from app.widget_props import rows_to_props
from app.widget_queries import SQL_COMPONENTS, display_props
from app.repositories import connections as conn_repo


DEMO_SCHEMA = """
PostgreSQL schema for the fallback SOC demo connection.
tables:
- servers(id, hostname, zone, criticality, owner, created_at)
- attack_events(id, server_id, attack_method, severity, occurred_at)
- incidents(id, title, status, severity, opened_at, asset_id)
- vulnerability_findings(id, cve, asset_id, score, status)
- blocked_ips(id, ip, reason, blocked_at, hit_count)
"""


class AgentRunError(RuntimeError):
    """A configured live model failed; do not hide it behind demo output."""


def _wid() -> str:
    return f"wgt_{secrets.token_hex(6)}"


def _aid() -> str:
    return f"art_{secrets.token_hex(6)}"


def _resolve_db_url(
    tenant_id: str,
    connection_id: str | None,
    role: str = "user",
) -> tuple[str, str | None, set[str] | None]:
    soc_default = {
        "servers",
        "attack_events",
        "incidents",
        "vulnerability_findings",
        "blocked_ips",
    }
    global_default = {"regions", "products", "monthly_sales"}

    if connection_id:
        row = conn_repo.get_connection(connection_id, tenant_id)
        if not row:
            raise ValueError("Database connection not found")
        allowed = conn_repo.allowed_tables_for_role(tenant_id, connection_id, role)
        if not allowed:
            allowed = global_default if connection_id == "dbconn_global" else soc_default
        return conn_repo.connection_url(row), connection_id, allowed

    # Prefer seeded demo connection
    demo = conn_repo.get_connection("dbconn_demo", tenant_id)
    if demo:
        allowed = conn_repo.allowed_tables_for_role(tenant_id, "dbconn_demo", role)
        if not allowed:
            allowed = soc_default
        return conn_repo.connection_url(demo), "dbconn_demo", allowed
    return DEMO_CUSTOMER_DATABASE_URL, None, soc_default


def _schema_text_for_connection(
    tenant_id: str,
    connection_id: str | None,
    allowed_tables: set[str] | None,
) -> str:
    """Build the LLM schema input from the selected connection's allowlist."""
    if not connection_id:
        return DEMO_SCHEMA
    row = conn_repo.get_connection(connection_id, tenant_id)
    if not row:
        return DEMO_SCHEMA
    return conn_repo.schema_context_for_connection(row, allowed_tables or set())


def _materialize_plan(
    plan: dict[str, Any],
    *,
    db_url: str,
    allowed_tables: set[str] | None,
    message: str,
    connection_id: str | None = None,
    evidence: list[dict[str, Any]] | None = None,
    deadline: float | None = None,
) -> tuple[str, dict[str, Any]]:
    summary = plan.get("summary") or "결과를 준비했습니다."
    widgets_in = plan.get("widgets") or []
    widgets: list[dict[str, Any]] = []

    for w in widgets_in:
        component = w.get("component")
        if component not in ALLOWED_COMPONENTS:
            component = "DataTable"
        title = w.get("title") or component
        sql = (w.get("sql") or "").strip()
        props = w.get("props") or {}
        if component in SQL_COMPONENTS and not sql:
            raise QueryError("Data widgets require a read-only SQL query")
        if sql:
            # Validate execution and the result contract for the existing repair
            # path, then discard rows. Renderers fetch their own current data.
            timeout_seconds = 10
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise BudgetExceeded("실행 시간 한도에 도달했습니다.")
                timeout_seconds = min(10, max(1, int(remaining)))
            rows = execute_readonly(db_url, sql, allowed_tables=allowed_tables, timeout_seconds=timeout_seconds)
            rows_to_props(component, rows, title)
            if evidence is not None:
                evidence.append({"component": component, "title": title, "sql": sql,
                                 "columns": list(rows[0]) if rows else [], "row_count": len(rows)})
            props = display_props(component, props)
        widgets.append(
            {
                "widget_id": w.get("widget_id") or _wid(),
                "component": component,
                "title": title,
                "sql": sql or None,
                **({"query_ref": {"connection_id": connection_id, "sql": sql}} if sql else {}),
                "props": props,
            }
        )

    # Document grounding for attack-like questions
    provider = get_document_provider()
    sources = provider.search(message, tenant_id="demo", limit=3)
    if "공격" in message or "attack" in message.lower() or any(
        "공격" in (w.get("title") or "") for w in widgets
    ):
        solution = build_solution_from_sources(sources)
        widgets.append(
            {
                "widget_id": _wid(),
                "component": "MarkdownBlock",
                "title": "해결 방안",
                "props": solution,
            }
        )
        if sources:
            widgets.append(
                {
                    "widget_id": _wid(),
                    "component": "SourceList",
                    "title": "문서 출처",
                    "props": {
                        "sources": [
                            {
                                "title": s["title"],
                                "version": s.get("version"),
                                "section": s.get("section"),
                            }
                            for s in sources
                        ]
                    },
                }
            )

    artifact = sanitize_artifact(
        {
            "artifact_id": _aid(),
            "type": plan.get("artifact_type") or "dashboard",
            "widgets": widgets,
        }
    )
    return summary, artifact


def _clarify(
    summary: str, message: str, probabilities: dict[str, float] | None,
    meta: dict[str, Any],
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    """Ask the user to pick a route instead of guessing. Stored with the message."""
    choices = choices_for(message, probabilities)
    return summary, {"type": "choices", "choices": choices, "widgets": []}, meta


def _answer_schema(
    message: str, schema_text: str, llm_context: dict[str, Any], meta: dict[str, Any],
    *, history: list[dict[str, Any]] | None = None,
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    """Explain the permitted schema in text; no SQL is run."""
    result = json_with_llm(
        SCHEMA_QA_HINT, {"question": message, "schema": schema_text, "history": history or []}, **llm_context,
    )
    answer = result.get("result") or {}
    if not answer.get("markdown"):
        raise AgentRunError(
            f"{result.get('provider') or 'LLM'} request failed: "
            f"{result.get('error') or 'schema answer was empty'}"
        )
    meta["provider"] = result.get("provider")
    meta["model"] = result.get("model")
    artifact = sanitize_artifact({
        "artifact_id": _aid(),
        "type": "report",
        "widgets": [{
            "widget_id": _wid(), "component": "MarkdownBlock",
            "title": "테이블 구조", "props": {"markdown": answer["markdown"]},
        }],
    })
    return answer.get("summary") or "테이블 구조를 설명했습니다.", artifact, meta


def _answer_general(
    message: str, llm_context: dict[str, Any], meta: dict[str, Any],
    *, history: list[dict[str, Any]] | None = None,
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    """Return a full conversational answer without SQL or widget generation."""
    result = json_with_llm(
        GENERAL_CHAT_HINT, {"question": message, "history": history or []}, **llm_context,
    )
    answer = result.get("result")
    content = answer.get("answer") if isinstance(answer, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise AgentRunError(
            f"{result.get('provider') or 'LLM'} request failed: "
            f"{result.get('error') or 'general answer was empty'}"
        )
    meta["provider"] = result.get("provider")
    meta["model"] = result.get("model")
    return content.strip(), {"type": "answer", "widgets": []}, meta


def _run_single(
    message: str,
    *,
    tenant_id: str,
    user_id: str,
    user_role: str = "user",
    conversation_id: str | None = None,
    connection_id: str | None = None,
    llm_settings: dict[str, str] | None = None,
    embedding_result: dict[str, Any] | None = None,
    forced_route: str | None = None,
    project_id: str | None = None,
    messages: list[dict[str, Any]] | None = None,
    expected_route: str | None = None,
    original_request: str | None = None,
    deadline: float,
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    meta: dict[str, Any] = {"provider": effective_provider()}
    db_url, used_conn, allowed = _resolve_db_url(tenant_id, connection_id, role=user_role)
    meta["connection_id"] = used_conn
    flow = conversation_flow(messages, used_conn)
    history = flow["history"]

    runtime_llm = llm_settings or {}

    llm_context = {
        "tenant_id": tenant_id, "user_id": user_id, "conversation_id": conversation_id,
        "runtime_provider": runtime_llm.get("provider"),
        "runtime_api_key": runtime_llm.get("api_key"),
        "runtime_model": runtime_llm.get("model"),
        "runtime_base_url": runtime_llm.get("base_url"),
    }
    try:
        decision = decide_route(
            message, tables=allowed or set(), forced_route=forced_route, llm_context=model_context(llm_context, deadline),
            history=history, last_route=flow["last_route"],
            jev_api_key=runtime_llm.get("jev_api_key"),
            expected_route=expected_route, original_request=original_request,
        )
    except RouteError as exc:
        raise AgentRunError(f"Could not decide how to handle the message: {exc}") from exc
    meta["route"] = "clarify" if decision["clarify"] else decision["route"]
    if decision["clarify"]:
        meta["route_candidate"] = decision["route"]
    meta["route_source"] = decision["source"]
    for key in ("confidence", "jev_error"):
        if decision.get(key) is not None:
            meta[f"route_{key}"] = decision[key]

    if decision["clarify"]:
        return _clarify(
            "무엇을 원하시는지 확실하지 않아요. 어떤 방식으로 처리할까요?",
            message, decision.get("probabilities"), meta,
        )
    if decision["route"] == "general_chat":
        return _answer_general(message, model_context(llm_context, deadline), meta, history=history)

    schema_text = _schema_text_for_connection(tenant_id, used_conn, allowed)
    if decision["route"] == "schema_qa":
        return _answer_schema(message, schema_text, model_context(llm_context, deadline), meta, history=history)

    # Expected-question similarity is only used here, to plan the SQL.
    retrieval = {"status": "no_connection", "matches": []}
    if used_conn and allowed:
        retrieval = question_similarity.search_questions(
            message, tenant_id=tenant_id, connection_id=used_conn,
            allowed_tables=allowed, llm_settings=runtime_llm,
            user_role=user_role, embedding_result=embedding_result,
        )
    meta["question_retrieval"] = retrieval

    # The current schema is already supplied separately. Keep references compact.
    references = [
        {"question": item["question"], "plan": item["plan"], "similarity": item["similarity"]}
        for item in retrieval["matches"]
    ]

    link = schema_linking.link_schema(
        message, retrieval["matches"], allowed or set(), tenant_id=tenant_id,
        project_id=project_id, llm_context=llm_context, history=history)
    meta["schema_link"] = {key: sorted(value) if key == "tables" else value for key, value in link.items()}
    plan_schema = schema_text if link["source"] == "full" else _schema_text_for_connection(
        tenant_id, used_conn, link["tables"])

    selection, selected_model = select_widgets(message, schema=plan_schema, history=history,
        references=references, context=llm_context, deadline=deadline)
    meta["widget_selection"] = {"count": len(selection["widgets"]),
                                "components": [w["component"] for w in selection["widgets"]]}
    meta.update(selected_model)
    evidence: list[dict[str, Any]] = []

    try:
        plan, sql_model = generate_sql(message, selection, schema=plan_schema, history=history,
            references=references, context=llm_context, deadline=deadline)
        summary, artifact = _materialize_plan(
            plan, db_url=db_url, allowed_tables=allowed, message=message, connection_id=used_conn,
            evidence=evidence, deadline=deadline,
        )
        meta.update(sql_model)
        meta["sql_generation"] = {"count": len(selection["widgets"]), "repaired": False}
        meta["result_evidence"] = evidence
        return summary, artifact, meta
    except BudgetExceeded:
        raise
    except Exception as first_exc:  # noqa: BLE001
        # Repair SQL against the full schema without changing widget selection.
        meta["schema_link"]["escalated_to_full"] = link["source"] != "full"
        try:
            plan2, repair_model = generate_sql(message, selection, schema=schema_text, history=history,
                references=references, context=llm_context, deadline=deadline,
                repair_hint=f"Previous SQL/result contract failed: {first_exc}. Fix SQL and JSON.")
            evidence = []
            summary, artifact = _materialize_plan(
                plan2, db_url=db_url, allowed_tables=allowed, message=message, connection_id=used_conn,
                evidence=evidence, deadline=deadline,
            )
            meta.update(repair_model)
            meta["retried"] = True
            meta["sql_generation"] = {"count": len(selection["widgets"]), "repaired": True}
            meta["result_evidence"] = evidence
            return summary, artifact, meta
        except BudgetExceeded:
            raise
        except Exception as second_exc:  # noqa: BLE001
            raise AgentRunError(
                f"SQL/plan failed after repair attempt: {second_exc}"
            ) from second_exc


def _merge_outputs(outputs):
    if len(outputs) == 1:
        return outputs[0]
    widgets = [widget for _, artifact in outputs for widget in artifact.get("widgets") or []]
    content = "\n\n".join(text for text, _ in outputs if text)
    if widgets:
        return content, sanitize_artifact({"type": "dashboard", "widgets": widgets})
    return content, {"type": "answer", "widgets": []}


def run_agent(
    message: str, *, tenant_id: str, user_id: str, user_role: str = "user",
    conversation_id: str | None = None, connection_id: str | None = None,
    llm_settings: dict[str, str] | None = None, embedding_result: dict[str, Any] | None = None,
    forced_route: str | None = None, project_id: str | None = None,
    messages: list[dict[str, Any]] | None = None,
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    """Plan → route → execute → evaluate; replan missing work within fixed limits."""
    deadline = time.monotonic() + LOOP_SECONDS
    settings = llm_settings or {}
    context = {"tenant_id": tenant_id, "user_id": user_id, "conversation_id": conversation_id,
        "runtime_provider": settings.get("provider"), "runtime_api_key": settings.get("api_key"),
        "runtime_model": settings.get("model"), "runtime_base_url": settings.get("base_url")}
    _, used_conn, _ = _resolve_db_url(tenant_id, connection_id, role=user_role)
    current_messages = list(messages or [])
    flow = conversation_flow(current_messages, used_conn)
    meta: dict[str, Any] = {"provider": effective_provider(), "connection_id": used_conn, "steps": []}
    outputs, done, seen = [], [], set()
    replans, stop, stop_reason = 0, "done", None
    try:
        plan = single_step_plan(forced_route, message) if forced_route else make_plan(message, flow, context, deadline)
        meta["plan"] = plan
        pending = list(plan["steps"])
        while pending:
            step = pending.pop(0)
            if time.monotonic() >= deadline or len(done) >= SAFETY_STEPS:
                stop, stop_reason = "budget", "실행 시간 또는 단계 한도에 도달했습니다."
                break
            if (step["route"], step["query"]) in seen:
                stop, stop_reason = "no_progress", "같은 작업이 반복되어 진행하지 못했습니다."
                break
            seen.add((step["route"], step["query"]))
            try:
                content, artifact, step_meta = _run_single(step["query"], tenant_id=tenant_id, user_id=user_id,
                    user_role=user_role, conversation_id=conversation_id, connection_id=connection_id,
                    llm_settings=settings, embedding_result=embedding_result if step["query"] == message else None,
                    forced_route=forced_route, project_id=project_id, messages=current_messages,
                    expected_route=step["route"], original_request=message, deadline=deadline)
            except (AgentRunError, DataPlanError) as exc:
                if not outputs:
                    raise AgentRunError(str(exc)) from exc
                stop, stop_reason = "incomplete", "남은 단계의 AI 처리 또는 SQL 생성에 실패했습니다."
                meta["steps"].append({"expected_route": step["route"], "status": "error",
                                      "verdict": "incomplete", "reason": stop_reason})
                break
            evidence = step_meta.pop("result_evidence", [])
            meta.update(step_meta)
            if artifact.get("type") == "choices":
                stop, stop_reason = "clarify", "처리 경로를 확인해야 합니다."
                meta["steps"].append({"expected_route": step["route"], "route": "clarify",
                                      "status": "needs_user", "verdict": "pause", "reason": stop_reason})
                if not outputs:
                    meta["loop_stop"] = "clarify"
                    return content, artifact, meta
                break
            route = step_meta["route"]
            record = {"query": step["query"], "route": route, "expected_route": step["route"],
                      "expect": step["expect"], "status": "ok", "content": content,
                      "widgets": artifact.get("widgets") or [], "sql_results": evidence}
            done.append(record)
            outputs.append((content, artifact))
            current_messages.extend([{"role": "user", "content": step["query"]},
                {"role": "assistant", "content": content, "artifact": artifact, "meta": step_meta}])
            step_trace = {"route": route, "expected_route": step["route"], "status": "ok",
                          "verdict": "incomplete", "reason": "목표 평가를 완료하지 못했습니다.",
                          **{key: step_meta[key] for key in ("widget_selection", "sql_generation") if key in step_meta}}
            meta["steps"].append(step_trace)
            verdict = evaluate(plan, done, len(pending), replans, context, deadline, user_request=message)
            step_trace.update(verdict=verdict["verdict"], reason=verdict["reason"])
            if verdict["verdict"] == "replan":
                pending = verdict["steps"]
                replans += 1
                meta["plan"] = {**plan, "replans": replans}
            elif verdict["verdict"] == "incomplete":
                stop, stop_reason = "incomplete", verdict["reason"]
                break
        meta["loop_stop"] = stop
    except BudgetExceeded:
        stop, stop_reason = "budget", "실행 시간 한도에 도달했습니다."
        meta["loop_stop"] = stop
    except PlanError as exc:
        if not outputs:
            raise AgentRunError(str(exc)) from exc
        stop, stop_reason = "incomplete", "원래 요청의 목표 충족 여부를 평가하지 못했습니다."
        meta["loop_stop"] = stop
    meta["replans"] = replans
    content, artifact = _merge_outputs(outputs) if outputs else ("", {"widgets": []})
    if stop_reason:
        notice = f"요청을 완료하지 못했습니다: {stop_reason}\n처리할 경로를 선택해 이어서 진행하세요."
        content = f"{content}\n\n{notice}" if content else notice
        artifact = {**artifact, "type": "choices", "choices": choices_for(message)}
    return content, artifact, meta
