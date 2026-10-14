"""Request Jev credentials must reach routing only, with no persisted secrets."""

import json

import pytest
from fastapi.testclient import TestClient

from app import agent_service, config, intent_router, main
from app.auth import get_current_user


@pytest.fixture
def chat_api(monkeypatch):
    saved, calls = [], []
    monkeypatch.setitem(main.app.dependency_overrides, get_current_user,
                        lambda: {"id": "owner", "tenant_id": "tenant", "role": "admin"})
    monkeypatch.setattr(main.conv_repo, "get_conversation", lambda *a: {"project_id": "project", "messages": []})
    monkeypatch.setattr(main.conv_repo, "touch_title_from_message", lambda *a: None)

    def add_message(conversation, role, content, artifact, meta=None):
        message = {"role": role, "content": content, "artifact": artifact, "meta": meta}
        saved.append(message)
        return message

    monkeypatch.setattr(main.conv_repo, "add_message", add_message)
    monkeypatch.setattr(main, "embed_text", lambda *a, **k: {"embedding": None, "error": None, "provider": "openai"})
    monkeypatch.setattr(agent_service, "_resolve_db_url", lambda *a, **k: ("db", "sales", {"orders"}))
    monkeypatch.setattr(agent_service, "_schema_text_for_connection", lambda *a: "orders(id)")

    def answer(hint, content, **settings):
        assert "jev_api_key" not in settings and "runtime_jev_api_key" not in settings
        assert "routing-test" not in json.dumps(content)
        assert "routing-test" not in json.dumps(settings)
        return {"result": {"markdown": "orders 테이블입니다."}, "provider": "openai", "model": "test-model"}

    monkeypatch.setattr(agent_service, "json_with_llm", answer)

    def route(*a, api_key, payload, **k):
        calls.append(api_key)
        assert "routing-test" not in json.dumps(payload)
        return {"answers": {"route": {"choice": "schema_qa", "confidence": 0.9}}}

    monkeypatch.setattr(intent_router.transport, "post_json", route)
    with TestClient(main.app) as client:
        yield client, saved, calls






def test_failed_request_key_is_scrubbed_and_does_not_reach_fallback_model(chat_api, monkeypatch):
    client, saved, calls = chat_api
    monkeypatch.setattr(config, "TYPESAFE_API_KEY", "")

    def failed_route(*a, **settings):
        raise RuntimeError("rejected request-routing-test")

    def fallback(hint, content, **settings):
        assert "routing-test" not in json.dumps({"content": content, "settings": settings})
        return {"result": {"route": "schema_qa"}}

    monkeypatch.setattr(intent_router.transport, "post_json", failed_route)
    monkeypatch.setattr(intent_router, "json_with_llm", fallback)
    response = client.post("/api/chat", headers={"X-Jev-API-Key": "request-routing-test"},
                           json={"conversation_id": "chat", "message": "테이블 구조는?"})
    assert response.status_code == 200
    assert response.json()["meta"]["route_source"] == "llm_fallback"
    assert "request-routing-test" not in json.dumps(response.json())
    assert "request-routing-test" not in json.dumps(saved)
