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

    monkeypatch.setattr(agent_service, "decide_route",
        lambda *args, **kwargs: {"route": "data_query", "source": "similarity", "clarify": False})
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
    monkeypatch.setattr(agent_service, "decide_route",
        lambda *args, **kwargs: {"route": "data_query", "source": "similarity", "clarify": False})
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


def test_local_chat_without_key_uses_selected_server(monkeypatch):
    from app.providers import transport
    calls, usage = [], []
    monkeypatch.setattr(llm, "log_usage", lambda **kwargs: usage.append(kwargs))
    monkeypatch.setattr(llm.config, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(llm.config, "LLM_API_KEY", "server-cloud-test-key")
    monkeypatch.setattr(transport, "post_json", lambda *args, **kwargs:
        calls.append((args, kwargs)) or {"choices": [{"message": {"content": '{"widgets": []}'}}]})
    result = llm.plan_with_llm("test", schema_text="orders(id)", tenant_id="t", user_id="u",
        conversation_id=None, runtime_provider="local", runtime_model="installed-model",
        runtime_base_url="http://model-server:1234/v1")
    assert result["provider"] == "local"
    assert result["plan"] == {"widgets": []}
    assert calls[0][0] == ("http://model-server:1234/v1", "/chat/completions")
    assert calls[0][1]["api_key"] == ""
    assert calls[0][1]["payload"]["model"] == "installed-model"
    assert usage[0]["success"] is True


def test_local_transport_omits_authorization(monkeypatch):
    from app.providers import transport
    calls = []
    class Client:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, url, **kwargs):
            calls.append(kwargs)
            return llm.httpx.Response(200, json={}, request=llm.httpx.Request("POST", url))
    monkeypatch.setattr(transport.httpx, "Client", Client)
    transport.post_json("http://localhost:11434/v1", "/chat/completions", api_key="", payload={})
    assert "Authorization" not in calls[0]["headers"]


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


def test_openai_custom_url_is_used_for_chat_and_embeddings(monkeypatch):
    from app.providers import transport
    calls = []
    monkeypatch.setattr(llm, "log_usage", lambda **kwargs: None)
    monkeypatch.setattr(llm.config, "CHAT_EMBEDDING_DIM", 3)
    def post(base, path, **kwargs):
        calls.append((base, path, kwargs))
        return {"data": [{"embedding": [1, 0, 0]}]} if path == "/embeddings" else {"choices": [{"message": {"content": '{"widgets": []}'}}]}
    monkeypatch.setattr(transport, "post_json", post)
    settings = dict(runtime_provider="openai", runtime_api_key="test-only", runtime_base_url="http://compatible:9000/v1")
    llm.plan_with_llm("test", schema_text="", tenant_id="t", user_id="u", conversation_id=None, **settings)
    result = llm.embed_text("test", **settings)
    assert result["error"] is None
    assert all(call[0] == "http://compatible:9000/v1" for call in calls)


def test_local_embeddings_require_model_and_exact_dimensions(monkeypatch):
    from app.providers import transport
    calls = []
    monkeypatch.setattr(llm.config, "CHAT_EMBEDDING_DIM", 3)
    monkeypatch.setattr(transport, "post_json", lambda *args, **kwargs:
        calls.append(kwargs) or {"data": [{"embedding": [1, 0]}]})
    settings = dict(runtime_provider="local", runtime_base_url="http://local:11434/v1")
    missing = llm.embed_text("test", runtime_embedding_model="", **settings)
    assert missing["embedding"] is None and "not configured" in missing["error"]
    assert calls == []
    mismatch = llm.embed_text("test", runtime_embedding_model="embed-local", **settings)
    assert mismatch["embedding"] is None and "CHAT_EMBEDDING_DIM=3" in mismatch["error"]
    assert calls[0]["payload"] == {"model": "embed-local", "input": ["test"]}


def test_local_model_error_keeps_provider_and_redacts_key(monkeypatch):
    from app.providers import transport
    usage = []
    monkeypatch.setattr(llm, "log_usage", lambda **kwargs: usage.append(kwargs))
    def fail(*args, **kwargs):
        raise ValueError("Invalid token test-private-key")
    monkeypatch.setattr(transport, "post_json", fail)
    result = llm.plan_with_llm("test", schema_text="", tenant_id="t", user_id="u",
        conversation_id=None, runtime_provider="local", runtime_model="installed-model",
        runtime_api_key="test-private-key")
    assert result["provider"] == "local" and result["plan"] is None
    assert "test-private-key" not in result["error"]
    assert "test-private-key" not in usage[0]["error"]


def test_local_repair_preserves_url_and_model(monkeypatch):
    calls = []
    monkeypatch.setattr(agent_service, "_resolve_db_url", lambda *args, **kwargs: ("db", "test", set()))
    monkeypatch.setattr(agent_service, "_schema_text_for_connection", lambda *args, **kwargs: "schema")
    monkeypatch.setattr(agent_service, "decide_route",
        lambda *args, **kwargs: {"route": "data_query", "source": "similarity", "clarify": False})
    monkeypatch.setattr(agent_service, "plan_with_llm", lambda *args, **kwargs:
        calls.append(kwargs) or {"plan": {"widgets": []}, "provider": "local"})
    def materialize(*args, **kwargs):
        if len(calls) == 1: raise ValueError("invalid SQL")
        return "ok", {"widgets": []}
    monkeypatch.setattr(agent_service, "_materialize_plan", materialize)
    agent_service.run_agent("test", tenant_id="t", user_id="u", llm_settings={
        "provider": "local", "model": "installed-model", "base_url": "http://local:11434/v1"})
    assert len(calls) == 2
    assert all(call["runtime_base_url"] == "http://local:11434/v1" and call["runtime_model"] == "installed-model" for call in calls)


def test_custom_url_does_not_receive_server_cloud_key(monkeypatch):
    from app.providers import resolve_provider
    import pytest
    monkeypatch.setattr(llm.config, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(llm.config, "LLM_API_KEY", "server-test-key")
    monkeypatch.setattr(llm.config, "LLM_BASE_URL", "https://api.openai.com/v1")
    with pytest.raises(ValueError, match="API key"):
        resolve_provider(runtime_provider="openai", runtime_base_url="http://other-server:9000/v1")


def test_local_settings_reach_chat_and_question_api(monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    from app.auth import get_current_user
    captured = []
    headers = {"X-LLM-Provider": "local", "X-LLM-Model": "local-chat",
               "X-LLM-Base-URL": "http://local:11434/v1", "X-LLM-Embedding-Model": "local-embed"}
    monkeypatch.setattr(main.conv_repo, "get_conversation", lambda *args: {"id": "test"})
    monkeypatch.setattr(main.conv_repo, "add_message", lambda *args, **kwargs: {"id": f"test-{args[1]}"})
    monkeypatch.setattr(main.conv_repo, "touch_title_from_message", lambda *args: None)
    def embed(*args, **kwargs):
        captured.append(("embed", kwargs))
        return {"embedding": None, "provider": "local", "error": None}
    monkeypatch.setattr(main, "embed_text", embed)
    def run(*args, **kwargs):
        captured.append(("chat", kwargs["llm_settings"]))
        return "test", {"widgets": []}, {"provider": "local"}
    monkeypatch.setattr(main, "run_agent", run)
    monkeypatch.setattr(main, "_question_context", lambda *args: {})
    monkeypatch.setattr(main.question_similarity, "seed_question_batch", lambda **kwargs:
        captured.append(("seed", kwargs["llm_settings"])) or {})
    previous = main.app.dependency_overrides.copy()
    main.app.dependency_overrides[get_current_user] = lambda: {"tenant_id": "t", "id": "u", "role": "admin"}
    try:
        with TestClient(main.app) as client:
            assert client.post("/api/chat", headers=headers, json={"conversation_id": "test", "message": "test"}).status_code == 200
            assert client.post("/api/database-connections/test/questions/seed", headers=headers, json={}).status_code == 200
    finally:
        main.app.dependency_overrides = previous
    assert len(captured) == 4
    for kind, settings in captured:
        assert settings["runtime_base_url" if kind == "embed" else "base_url"] == headers["X-LLM-Base-URL"]
        assert settings["runtime_embedding_model" if kind == "embed" else "embedding_model"] == "local-embed"


def test_local_embedding_response_is_validated_and_normalized(monkeypatch):
    from app.providers import transport
    monkeypatch.setattr(llm.config, "CHAT_EMBEDDING_DIM", 3)
    monkeypatch.setattr(transport, "post_json", lambda *args, **kwargs: {"data": [
        {"index": 1, "embedding": [0, 2, 0]}, {"index": 0, "embedding": [2, 0, 0]}]})
    result = llm.embed_texts(["first", "second"], runtime_provider="local",
        runtime_embedding_model="embed-local")
    assert result["error"] is None
    assert result["model"] == "embed-local" and result["provider"] == "local"
    assert result["embeddings"] == [[1, 0, 0], [0, 1, 0]]


def test_empty_request_overrides_keep_server_configuration(monkeypatch):
    from app.providers import resolve_provider
    monkeypatch.setattr(llm.config, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(llm.config, "LLM_API_KEY", "server-test-key")
    monkeypatch.setattr(llm.config, "LLM_BASE_URL", "http://server-compatible:9000/v1")
    monkeypatch.setattr(llm.config, "LLM_MODEL", "server-model")
    adapter = resolve_provider(runtime_provider="", runtime_api_key="", runtime_model="", runtime_base_url="")
    assert adapter.api_key == "server-test-key"
    assert adapter.model == "server-model"
    assert adapter.base_url == "http://server-compatible:9000/v1"
