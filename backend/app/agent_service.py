"""Orchestrate mock/LLM planning, SQL execution, and document grounding."""

from __future__ import annotations

import secrets
from typing import Any

from app.agent import sanitize_artifact
from app import question_similarity
from app.config import ALLOWED_COMPONENTS, DEMO_CUSTOMER_DATABASE_URL
from app.documents import build_solution_from_sources, get_document_provider
from app.intent_router import RouteError, choices_for, decide_route
from app.llm import effective_provider, json_with_llm, plan_with_llm
from app.prompts import SCHEMA_QA_HINT
from app.query import QueryError, execute_readonly
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


def rows_to_props(component: str, rows: list[dict[str, Any]], title: str) -> dict[str, Any]:
    if not rows:
        if component == "KpiStat":
            return {"label": title, "value": 0}
        if component == "DataTable":
            return {"columns": [{"key": "info", "label": "Info"}], "rows": [{"info": "결과 없음"}]}
        if component == "BarChart":
            return {"categories": [], "series": [{"name": "value", "data": []}]}
        if component == "LineChart":
            return {"series": [{"name": title, "points": []}]}
        if component == "RankList":
            return {"items": []}
        if component == "PieChart":
            return {"slices": []}
        return {}

    keys = list(rows[0].keys())
    if component == "KpiStat":
        value_key = "value" if "value" in keys else keys[-1]
        return {"label": title, "value": rows[0][value_key], "unit": rows[0].get("unit")}
    if component == "DataTable":
        return {
            "columns": [{"key": k, "label": k} for k in keys],
            "rows": [{k: r.get(k) for k in keys} for r in rows],
        }
    if component == "RankList":
        label_key = "hostname" if "hostname" in keys else keys[0]
        value_key = "attack_count" if "attack_count" in keys else keys[-1]
        meta_key = "top_method" if "top_method" in keys else None
        items = []
        for i, r in enumerate(rows, start=1):
            items.append(
                {
                    "rank": i,
                    "label": str(r.get(label_key)),
                    "value": r.get(value_key),
                    "meta": str(r.get(meta_key)) if meta_key else None,
                }
            )
        return {"items": items}
    if component == "BarChart":
        cat_key = "hostname" if "hostname" in keys else keys[0]
        val_key = "attack_count" if "attack_count" in keys else keys[-1]
        return {
            "categories": [str(r.get(cat_key)) for r in rows],
            "series": [{"name": val_key, "data": [r.get(val_key) or 0 for r in rows]}],
        }
    if component == "LineChart":
        x_key = "x" if "x" in keys else keys[0]
        y_key = "y" if "y" in keys else keys[-1]
        return {
            "series": [
                {
                    "name": title,
                    "points": [{"x": str(r.get(x_key)), "y": r.get(y_key)} for r in rows],
                }
            ]
        }
    if component == "PieChart":
        label_key = keys[0]
        value_key = keys[-1]
        return {
            "slices": [
                {"label": str(r.get(label_key)), "value": r.get(value_key) or 0} for r in rows
            ]
        }
    if component == "PieTable":
        label_key = "label" if "label" in keys else keys[0]
        value_key = "value" if "value" in keys else keys[-1]
        slices = [
            {"label": str(r.get(label_key)), "value": r.get(value_key) or 0} for r in rows
        ]
        return {
            "slices": slices,
            "columns": [
                {"key": "label", "label": label_key},
                {"key": "value", "label": value_key},
            ],
            "rows": slices,
        }
    if component == "BarTable":
        cat_key = "hostname" if "hostname" in keys else ("label" if "label" in keys else keys[0])
        val_key = "attack_count" if "attack_count" in keys else ("value" if "value" in keys else keys[-1])
        meta_key = "top_method" if "top_method" in keys else None
        categories = [str(r.get(cat_key)) for r in rows]
        data = [r.get(val_key) or 0 for r in rows]
        table_rows = [
            {
                "label": str(r.get(cat_key)),
                "value": r.get(val_key),
                **({"meta": r.get(meta_key)} if meta_key else {}),
            }
            for r in rows
        ]
        cols = [
            {"key": "label", "label": cat_key},
            {"key": "value", "label": val_key},
        ]
        if meta_key:
            cols.append({"key": "meta", "label": meta_key})
        return {
            "label": title,
            "value": sum(data) if data else 0,
            "categories": categories,
            "series": [{"name": val_key, "data": data}],
            "columns": cols,
            "rows": table_rows,
        }
    if component == "KpiSparkline":
        value_key = "value" if "value" in keys else keys[-1]
        points = []
        if "x" in keys and "y" in keys:
            points = [{"x": str(r.get("x")), "y": r.get("y")} for r in rows]
        return {
            "label": title,
            "value": rows[0].get(value_key),
            "points": points
            or [{"x": str(i), "y": r.get(value_key) or 0} for i, r in enumerate(rows)],
        }
    return {"columns": [{"key": k, "label": k} for k in keys], "rows": rows}


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
) -> tuple[str, dict[str, Any]]:
    summary = plan.get("summary") or "결과를 준비했습니다."
    widgets_in = plan.get("widgets") or []
    widgets: list[dict[str, Any]] = []
    sql_error: str | None = None

    for w in widgets_in:
        component = w.get("component")
        if component not in ALLOWED_COMPONENTS:
            component = "DataTable"
        title = w.get("title") or component
        sql = (w.get("sql") or "").strip()
        props = w.get("props") or {}
        if sql:
            try:
                rows = execute_readonly(
                    db_url, sql, allowed_tables=allowed_tables
                )
                props = rows_to_props(component, rows, title)
            except (QueryError, Exception) as exc:  # noqa: BLE001
                sql_error = str(exc)
                raise
        widgets.append(
            {
                "widget_id": w.get("widget_id") or _wid(),
                "component": component,
                "title": title,
                "sql": sql or None,
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
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    """Explain the permitted schema in text; no SQL is run."""
    result = json_with_llm(
        SCHEMA_QA_HINT, {"question": message, "schema": schema_text}, **llm_context,
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


def run_agent(
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
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    meta: dict[str, Any] = {"provider": effective_provider()}

    db_url, used_conn, allowed = _resolve_db_url(tenant_id, connection_id, role=user_role)
    meta["connection_id"] = used_conn

    runtime_llm = llm_settings or {}
    schema_text = _schema_text_for_connection(tenant_id, used_conn, allowed)

    retrieval = {"status": "no_connection", "matches": []}
    if used_conn and allowed:
        retrieval = question_similarity.search_questions(
            message, tenant_id=tenant_id, connection_id=used_conn,
            allowed_tables=allowed, llm_settings=runtime_llm,
            user_role=user_role, embedding_result=embedding_result,
        )
    meta["question_retrieval"] = retrieval

    llm_context = {
        "tenant_id": tenant_id, "user_id": user_id, "conversation_id": conversation_id,
        "runtime_provider": runtime_llm.get("provider"),
        "runtime_api_key": runtime_llm.get("api_key"),
        "runtime_model": runtime_llm.get("model"),
        "runtime_base_url": runtime_llm.get("base_url"),
    }
    try:
        decision = decide_route(
            message, tables=allowed or set(), forced_route=forced_route,
            similar_matched=retrieval["status"] == "matched", llm_context=llm_context,
        )
    except RouteError as exc:
        raise AgentRunError(f"Could not decide how to handle the message: {exc}") from exc
    meta["route"] = "clarify" if decision["clarify"] else decision["route"]
    meta["route_source"] = decision["source"]
    for key in ("confidence", "jev_error"):
        if decision.get(key) is not None:
            meta[f"route_{key}"] = decision[key]

    if decision["clarify"]:
        return _clarify(
            "무엇을 원하시는지 확실하지 않아요. 어떤 방식으로 처리할까요?",
            message, decision.get("probabilities"), meta,
        )
    if decision["route"] == "knowledge_qa":
        return _clarify(
            "문서(지식그래프) 검색은 아직 채팅에 연결되지 않았어요. 다른 방식으로 처리할까요?",
            message, None, meta,
        )
    if decision["route"] == "schema_qa":
        return _answer_schema(message, schema_text, llm_context, meta)

    # The current schema is already supplied separately. Keep references compact.
    references = [
        {"question": item["question"], "plan": item["plan"], "similarity": item["similarity"]}
        for item in retrieval["matches"]
    ]

    llm_result = plan_with_llm(
        message,
        schema_text=schema_text,
        tenant_id=tenant_id,
        user_id=user_id,
        conversation_id=conversation_id,
        runtime_provider=runtime_llm.get("provider"),
        runtime_api_key=runtime_llm.get("api_key"),
        runtime_model=runtime_llm.get("model"),
        runtime_base_url=runtime_llm.get("base_url"),
        matched_questions=references,
    )
    plan = llm_result.get("plan")
    if not plan:
        raise AgentRunError(
            f"{llm_result.get('provider') or 'LLM'} request failed: "
            f"{llm_result.get('error') or 'No AI provider configured'}"
        )

    try:
        summary, artifact = _materialize_plan(
            plan, db_url=db_url, allowed_tables=allowed, message=message
        )
        meta["provider"] = llm_result.get("provider")
        meta["model"] = llm_result.get("model")
        return summary, artifact, meta
    except Exception as first_exc:  # noqa: BLE001
        repair = plan_with_llm(
            message,
            schema_text=schema_text,
            tenant_id=tenant_id,
            user_id=user_id,
            conversation_id=conversation_id,
            repair_hint=f"Previous SQL/plan failed: {first_exc}. Fix SQL and JSON.",
            runtime_provider=runtime_llm.get("provider"),
            runtime_api_key=runtime_llm.get("api_key"),
            runtime_model=runtime_llm.get("model"),
            runtime_base_url=runtime_llm.get("base_url"),
            matched_questions=references,
        )
        plan2 = repair.get("plan")
        if not plan2:
            raise AgentRunError(
                f"SQL/plan failed and repair attempt returned no plan: {first_exc}"
            ) from first_exc
        try:
            summary, artifact = _materialize_plan(
                plan2, db_url=db_url, allowed_tables=allowed, message=message
            )
            meta["provider"] = repair.get("provider")
            meta["retried"] = True
            return summary, artifact, meta
        except Exception as second_exc:  # noqa: BLE001
            raise AgentRunError(
                f"SQL/plan failed after repair attempt: {second_exc}"
            ) from second_exc
