import json

from app import agent_plan, agent_service, llm






def test_live_model_error_is_not_hidden_by_mock(monkeypatch):
    monkeypatch.setattr(agent_service, "_resolve_db_url", lambda *args, **kwargs: ("db", "test", set()))
    monkeypatch.setattr(agent_service, "effective_provider", lambda: "mock")
    monkeypatch.setattr(agent_service, "_schema_text_for_connection", lambda *args, **kwargs: "schema")
    monkeypatch.setattr(agent_service, "decide_route",
        lambda *args, **kwargs: {"route": "data_query", "source": "similarity", "clarify": False})
    monkeypatch.setattr(
        agent_plan,
        "json_with_llm",
        lambda *args, **kwargs: {"provider": "gemini", "result": None, "error": "HTTP 404: model unavailable"},
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






def test_missing_cloud_key_is_failure_without_cross_provider_fallback(monkeypatch):
    from app.providers import transport
    usage = []
    monkeypatch.setattr(llm, "log_usage", lambda **kwargs: usage.append(kwargs))
    monkeypatch.setattr(llm.config, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(llm.config, "LLM_API_KEY", "server-gemini-test-key")
    monkeypatch.setattr(transport, "post_json", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Must not send")))
    result = llm.plan_with_llm("test", schema_text="", tenant_id="t", user_id="u",
        conversation_id=None, runtime_provider="openai")
    assert result["plan"] is None
    assert result["provider"] == "openai"
    assert "API key" in result["error"]
    assert usage[0]["success"] is False















