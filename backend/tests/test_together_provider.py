"""Together request compatibility and credential isolation without external calls."""

import pytest

from app import config
from app.providers import resolve_provider, transport


def test_together_chat_uses_own_endpoint_and_does_not_reuse_another_provider_key(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(config, "LLM_API_KEY", "test-openai-only")
    calls = []
    monkeypatch.setattr(transport, "post_json", lambda base, path, **kwargs: calls.append(
        (base, path, kwargs)) or {"choices": [{"message": {"content": '{"ok":true}'}}]})
    with pytest.raises(ValueError, match="API key is required"):
        resolve_provider(runtime_provider="together")
    assert calls == []
    adapter = resolve_provider(runtime_provider="together", runtime_api_key="test-together-only")
    result, _ = adapter.plan("Return JSON", {"question": "hello"})
    assert result == {"ok": True}
    base, path, request = calls[0]
    assert base == "https://api.together.ai/v1" and path == "/chat/completions"
    assert request["api_key"] == "test-together-only"
    assert request["payload"]["model"] == "Qwen/Qwen3.5-9B"
    assert request["payload"]["response_format"] == {"type": "json_object"}
    with pytest.raises(ValueError, match="serverless embeddings are unavailable"):
        adapter.embed(["text"], 2)
    assert len(calls) == 1


def test_together_custom_endpoint_does_not_receive_the_server_key(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "together")
    monkeypatch.setattr(config, "LLM_API_KEY", "test-server-only")
    monkeypatch.setattr(config, "LLM_BASE_URL", "https://api.together.ai/v1")
    with pytest.raises(ValueError, match="API key is required"):
        resolve_provider(runtime_provider="together", runtime_base_url="http://localhost:12345/v1")
    adapter = resolve_provider(runtime_provider="together", runtime_api_key="test-dedicated-only",
        runtime_base_url="http://localhost:12345/v1", runtime_model="dedicated-chat")
    assert adapter.api_key == "test-dedicated-only" and adapter.model == "dedicated-chat"
    assert adapter.base_url == "http://localhost:12345/v1"


def test_together_dedicated_embeddings_preserve_native_dimensions_and_order(monkeypatch):
    calls = []
    monkeypatch.setattr(transport, "post_json", lambda base, path, **kwargs: calls.append(kwargs) or {
        "data": [{"index": 1, "embedding": [0, 2]}, {"index": 0, "embedding": [2, 0]}]})
    adapter = resolve_provider(runtime_provider="together", runtime_api_key="test-only",
        runtime_embedding_model="dedicated-embedding")
    assert adapter.embed(["first", "second"], 2) == [[1, 0], [0, 1]]
    assert calls[0]["payload"] == {"model": "dedicated-embedding", "input": ["first", "second"]}
    with pytest.raises(ValueError, match="embedding dimension must match 1"):
        adapter.embed(["first", "second"], 1)
