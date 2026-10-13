"""Follow-up context across the API, routing, SQL planning and repair paths."""

import json

import pytest
from fastapi.testclient import TestClient

from app import agent_service, config, intent_router, llm, main
from app.auth import get_current_user
from app.chat_flow import conversation_flow


def turn(connection_id="sales", question="고객별 주문 상위 10개", route="data_query"):
    return [
        {"role": "user", "content": question},
        {"role": "assistant", "content": "고객별 주문 순위입니다.",
         "meta": {"connection_id": connection_id, "route": route, "api_key": "do-not-copy"},
         "artifact": {"widgets": [{"component": "DataTable", "title": "고객별 주문",
             "sql": "SELECT customer_id, count(*) FROM orders GROUP BY customer_id ORDER BY count(*) DESC LIMIT 10",
             "props": {"rows": [{"customer_id": "do-not-copy"}]}}]}},
    ]


def test_context_keeps_query_meaning_and_markdown_without_rows_or_diagnostics():
    messages = turn()
    messages[-1]["artifact"]["widgets"].append({"component": "MarkdownBlock", "title": "구조",
                                                "props": {"markdown": "orders.customer_id는 고객 ID입니다."}})
    flow = conversation_flow(messages, "sales")
    assert flow["last_route"] == "data_query"
    assert flow["history"][0] == {"role": "user", "content": messages[0]["content"]}
    assert flow["history"][1]["widgets"][0]["sql"] == messages[-1]["artifact"]["widgets"][0]["sql"]
    assert flow["history"][1]["widgets"][1]["markdown"].startswith("orders.customer_id")
    assert "do-not-copy" not in json.dumps(flow)


def test_context_stops_at_db_changes_and_does_not_resurrect_earlier_db_turns():
    messages = turn() + turn("other", "서버 수") + turn(question="제품별 주문")
    flow = conversation_flow(messages, "sales")
    assert [entry["content"] for entry in flow["history"]] == ["제품별 주문", "고객별 주문 순위입니다."]
    assert conversation_flow(messages, "new-db") == {"last_route": None, "history": []}


def test_legacy_unknown_db_and_failed_unanswered_turns_are_not_context():
    legacy = turn()
    legacy[-1]["meta"].pop("connection_id")
    messages = legacy + [{"role": "user", "content": "실패한 질문"}] + turn() + [
        {"role": "user", "content": "최근 실패한 질문"}]
    assert conversation_flow(legacy, "sales")["history"] == []
    assert conversation_flow(messages, "sales")["history"] == conversation_flow(turn(), "sales")["history"]


def test_history_uses_only_the_latest_twenty_messages():
    messages = [message for number in range(15) for message in turn(question=str(number))]
    flow = conversation_flow(messages, "sales")
    assert len(flow["history"]) == 20
    assert flow["history"][0]["content"] == "5"
    assert flow["history"][-2]["content"] == "14"
    assert conversation_flow([], "sales") == {"last_route": None, "history": []}


@pytest.mark.parametrize("use_jev", [True, False])
def test_router_passes_followup_history_to_jev_and_llm(monkeypatch, use_jev):
    flow = conversation_flow(turn(), "sales")
    captured = []
    monkeypatch.setattr(config, "TYPESAFE_API_KEY", "test-only" if use_jev else "")
    monkeypatch.setattr(intent_router.transport, "post_json", lambda *a, **k:
        captured.append(k["payload"]["state"]) or {"answers": {"route": {
            "choice": "data_query", "confidence": 0.9}}})
    monkeypatch.setattr(intent_router, "json_with_llm", lambda hint, state, **k:
        captured.append(state) or {"result": {"route": "data_query"}})
    decision = intent_router.decide_route("그중 상위 5개만", tables={"orders"}, forced_route=None,
        llm_context={}, history=flow["history"], last_route=flow["last_route"])
    assert decision["route"] == "data_query"
    assert captured[0]["question"] == "그중 상위 5개만"
    assert captured[0]["last_route"] == "data_query"
    assert captured[0]["recent_turns"] == flow["history"]


def test_followup_sql_and_repair_keep_history_and_prior_permitted_tables(monkeypatch):
    messages = turn()
    allowed = {"orders", "products"} | {f"table_{i}" for i in range(30)}
    plans, routing = [], []
    monkeypatch.setattr(agent_service, "_resolve_db_url", lambda *a, **k: ("db", "sales", allowed))
    monkeypatch.setattr(agent_service, "_schema_text_for_connection", lambda tenant, conn, tables: sorted(tables))
    monkeypatch.setattr(agent_service.question_similarity, "search_questions", lambda *a, **k:
        {"status": "matched", "matches": [{"question": "제품 순위", "similarity": 0.9,
          "plan": {"widgets": [{"sql": "SELECT * FROM products"}]}}]})
    monkeypatch.setattr(agent_service, "decide_route", lambda *a, **k:
        routing.append(k) or {"route": "data_query", "source": "jev", "clarify": False})
    monkeypatch.setattr(llm, "json_with_llm", lambda hint, content, **k:
        plans.append(content) or {"result": {"widgets": []}, "provider": "openai"})

    def materialize(*a, **k):
        if len(plans) == 1:
            raise ValueError("retry with full schema")
        return "고객 상위 5개", {"widgets": []}

    monkeypatch.setattr(agent_service, "_materialize_plan", materialize)
    _, _, meta = agent_service.run_agent("그중 상위 5개만", tenant_id="t", user_id="u", messages=messages)
    history = conversation_flow(messages, "sales")["history"]
    assert routing[0]["history"] == history and routing[0]["last_route"] == "data_query"
    assert len(plans) == 2 and all(plan["history"] == history for plan in plans)
    assert plans[0]["schema"] == ["orders", "products"]
    assert plans[1]["schema"] == sorted(allowed)
    assert meta["retried"] and meta["schema_link"]["escalated_to_full"]


def test_schema_followup_receives_history_even_with_explicit_route(monkeypatch):
    messages = turn(route="schema_qa")
    calls = []
    monkeypatch.setattr(agent_service, "_resolve_db_url", lambda *a, **k: ("db", "sales", {"orders"}))
    monkeypatch.setattr(agent_service, "_schema_text_for_connection", lambda *a: "orders(customer_id)")
    monkeypatch.setattr(agent_service, "json_with_llm", lambda hint, content, **k:
        calls.append(content) or {"result": {"markdown": "고객 ID입니다."}, "provider": "openai"})
    monkeypatch.setattr(intent_router.transport, "post_json", lambda *a, **k: pytest.fail("explicit route"))
    agent_service.run_agent("그 컬럼은?", tenant_id="t", user_id="u", messages=messages, forced_route="schema_qa")
    assert calls[0]["history"] == conversation_flow(messages, "sales")["history"]
    assert calls[0]["schema"] == "orders(customer_id)"


def test_chat_api_uses_owned_history_and_persists_db_identity(monkeypatch):
    messages, runs, lookups, saved = turn(), [], [], []
    user = {"id": "owner", "tenant_id": "tenant", "role": "admin"}
    monkeypatch.setitem(main.app.dependency_overrides, get_current_user, lambda: user)
    monkeypatch.setattr(main.conv_repo, "get_conversation", lambda *a:
        lookups.append(a) or {"project_id": "project", "messages": list(messages)})
    monkeypatch.setattr(main.conv_repo, "touch_title_from_message", lambda *a: None)

    def add_message(conversation_id, role, content, artifact, meta=None):
        entry = {"role": role, "content": content, "artifact": artifact, "meta": meta}
        saved.append(entry)
        messages.append(entry)
        return entry

    monkeypatch.setattr(main.conv_repo, "add_message", add_message)
    monkeypatch.setattr(main, "embed_text", lambda *a, **k: {"embedding": None, "error": None, "provider": "openai"})
    monkeypatch.setattr(main, "run_agent", lambda message, **k:
        runs.append(k) or ("답변", {"widgets": []}, {"connection_id": "sales", "route": "data_query"}))
    with TestClient(main.app) as client:
        response = client.post("/api/chat", json={"conversation_id": "chat", "message": "그중 상위 5개만",
                                                   "connection_id": "sales"})
    assert response.status_code == 200
    assert lookups == [("chat", "tenant", "owner")]
    assert runs[0]["messages"] == turn()  # current user message is excluded
    assert saved[-1]["meta"] == {"connection_id": "sales", "route": "data_query"}
    assert conversation_flow(messages, "sales")["history"][-2]["content"] == "그중 상위 5개만"
