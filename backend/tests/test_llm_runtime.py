import json

from app import agent_service, llm


def test_gemini_uses_its_endpoint_and_reports_provider(monkeypatch):
    calls = []
    monkeypatch.setattr(llm, "log_usage", lambda **kwargs: None)

    class Client:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url, **kwargs):
            calls.append((url, kwargs))
            return llm.httpx.Response(200, json={
                "choices": [{"message": {"content": json.dumps({"widgets": []})}}],
            }, request=llm.httpx.Request("POST", url))

    monkeypatch.setattr(llm.httpx, "Client", Client)
    result = llm.plan_with_llm("test", schema_text="", tenant_id="test",
        user_id="test", conversation_id=None, runtime_provider="gemini",
        runtime_api_key="test-key")
    assert result["provider"] == "gemini"
    assert calls[0][0] == "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    assert calls[0][1]["headers"]["Authorization"] == "Bearer test-key"
    assert calls[0][1]["json"]["model"] == "gemini-3.6-flash"


def test_repair_keeps_runtime_credentials(monkeypatch):
    calls = []
    monkeypatch.setattr(agent_service, "_resolve_db_url", lambda *args, **kwargs: ("db", "test", set()))
    monkeypatch.setattr(agent_service, "effective_provider", lambda: "mock")
    monkeypatch.setattr(agent_service, "_schema_text_for_connection", lambda *args, **kwargs: "schema")

    def plan(*args, **kwargs):
        calls.append(kwargs)
        return {"plan": {"widgets": []}, "provider": "gemini"}

    def materialize(*args, **kwargs):
        if len(calls) == 1:
            raise ValueError("invalid SQL")
        return "ok", {"widgets": []}

    monkeypatch.setattr(agent_service, "plan_with_llm", plan)
    monkeypatch.setattr(agent_service, "_materialize_plan", materialize)
    _, _, meta = agent_service.run_agent("test", tenant_id="test", user_id="test",
        llm_settings={"provider": "gemini", "api_key": "test-key", "model": "test-model"})
    assert meta["retried"]
    assert len(calls) == 2
    for call in calls:
        assert call["runtime_api_key"] == "test-key"
        assert call["runtime_provider"] == "gemini"
        assert call["runtime_model"] == "test-model"


def test_live_model_error_is_not_hidden_by_mock(monkeypatch):
    monkeypatch.setattr(agent_service, "_resolve_db_url", lambda *args, **kwargs: ("db", "test", set()))
    monkeypatch.setattr(agent_service, "effective_provider", lambda: "mock")
    monkeypatch.setattr(agent_service, "_schema_text_for_connection", lambda *args, **kwargs: "schema")
    monkeypatch.setattr(
        agent_service,
        "plan_with_llm",
        lambda *args, **kwargs: {"provider": "gemini", "plan": None, "error": "HTTP 404: model unavailable"},
    )

    import pytest

    with pytest.raises(agent_service.AgentRunError, match="HTTP 404"):
        agent_service.run_agent(
            "test",
            tenant_id="tenant",
            user_id="user",
            connection_id="test",
            llm_settings={"provider": "gemini", "api_key": "test-key"},
        )
