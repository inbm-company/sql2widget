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




def test_context_stops_at_db_changes_and_does_not_resurrect_earlier_db_turns():
    messages = turn() + turn("other", "서버 수") + turn(question="제품별 주문")
    flow = conversation_flow(messages, "sales")
    assert [entry["content"] for entry in flow["history"]] == ["제품별 주문", "고객별 주문 순위입니다."]
    assert conversation_flow(messages, "new-db") == {"last_route": None, "history": []}












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
