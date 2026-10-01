import httpx
import pytest

from app import agent_service, config, intent_router as router

CTX = {"tenant_id": "t", "user_id": "u", "conversation_id": None}


def response(status, body=None):
    request = httpx.Request("POST", "https://api.typesafe.ai/v1/systemone")
    return httpx.Response(status, json=body or {}, request=request)


def jev_body(choice="data_query", confidence=0.9, **probabilities):
    return {"answers": {"route": {
        "choice": choice, "confidence": confidence, "probabilities": probabilities,
    }}}


@pytest.fixture(autouse=True)
def jev_key(monkeypatch):
    monkeypatch.setattr(config, "TYPESAFE_API_KEY", "test-key")
    monkeypatch.setattr(router.time, "sleep", lambda seconds: None)


def decide(**overrides):
    args = {"tables": {"orders"}, "similar_matched": False, "forced_route": None,
            "llm_context": CTX}
    return router.decide_route("질문", **{**args, **overrides})


def post_json_returning(monkeypatch, *outcomes):
    calls = []

    def post_json(*args, **kwargs):
        calls.append(kwargs)
        outcome = outcomes[min(len(calls), len(outcomes)) - 1]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(router.transport, "post_json", post_json)
    return calls


def test_user_choice_and_similarity_skip_every_model(monkeypatch):
    calls = post_json_returning(monkeypatch, jev_body())
    assert decide(forced_route="schema_qa") == {
        "route": "schema_qa", "source": "user_choice", "clarify": False}
    assert decide(similar_matched=True)["source"] == "similarity"
    assert calls == []


def test_jev_choice_is_used_with_its_confidence(monkeypatch):
    calls = post_json_returning(monkeypatch, jev_body("schema_qa", 0.8))
    result = decide()
    assert (result["route"], result["source"], result["clarify"]) == ("schema_qa", "jev", False)
    assert calls[0]["api_key"] == "test-key"
    assert calls[0]["payload"]["state"]["tables"] == ["orders"]


def test_low_confidence_or_other_asks_the_user(monkeypatch):
    post_json_returning(monkeypatch, jev_body("data_query", 0.3))
    assert decide()["clarify"] is True
    post_json_returning(monkeypatch, jev_body("other", 0.99))
    assert decide()["clarify"] is True


def test_retries_twice_on_overload_then_succeeds(monkeypatch):
    overloaded = httpx.HTTPStatusError("busy", request=response(529).request, response=response(529))
    calls = post_json_returning(monkeypatch, overloaded, overloaded, jev_body())
    assert decide()["source"] == "jev"
    assert len(calls) == 3


def test_auth_errors_are_not_retried_and_fall_back_to_llm(monkeypatch):
    unauthorized = httpx.HTTPStatusError("no", request=response(401).request, response=response(401))
    calls = post_json_returning(monkeypatch, unauthorized)
    monkeypatch.setattr(router, "json_with_llm", lambda *a, **k: {"result": {"route": "schema_qa"}})
    result = decide()
    assert len(calls) == 1
    assert (result["route"], result["source"]) == ("schema_qa", "llm_fallback")
    assert "401" in result["jev_error"]
    assert "test-key" not in result["jev_error"]


def test_missing_key_uses_llm_and_records_why(monkeypatch):
    monkeypatch.setattr(config, "TYPESAFE_API_KEY", "")
    monkeypatch.setattr(router, "json_with_llm", lambda *a, **k: {"result": {"route": "data_query"}})
    result = decide()
    assert result["source"] == "llm_fallback"
    assert result["jev_error"] == "TYPESAFE_API_KEY is not configured"


def test_both_models_failing_raises(monkeypatch):
    monkeypatch.setattr(config, "TYPESAFE_API_KEY", "")
    monkeypatch.setattr(router, "json_with_llm", lambda *a, **k: {"result": None, "error": "boom"})
    with pytest.raises(router.RouteError, match="boom"):
        decide()


def test_choices_put_the_likeliest_route_first():
    choices = router.choices_for("질문", {"schema_qa": 0.6, "data_query": 0.3})
    assert [c["route"] for c in choices] == ["schema_qa", "data_query"]
    assert all(c["message"] == "질문" for c in choices)


def agent_with(monkeypatch, decision):
    monkeypatch.setattr(agent_service, "_resolve_db_url", lambda *a, **k: ("db", "test", set()))
    monkeypatch.setattr(agent_service, "_schema_text_for_connection", lambda *a, **k: "schema")
    monkeypatch.setattr(agent_service, "decide_route", lambda *a, **k: decision)
    return lambda: agent_service.run_agent("질문", tenant_id="t", user_id="u")


def test_clarify_returns_choices_without_running_sql(monkeypatch):
    monkeypatch.setattr(agent_service, "plan_with_llm", lambda *a, **k: pytest.fail("no plan"))
    run = agent_with(monkeypatch, {"route": "other", "source": "jev", "clarify": True,
                                   "confidence": 0.4, "probabilities": {}})
    summary, artifact, meta = run()
    assert artifact["type"] == "choices" and artifact["widgets"] == []
    assert meta["route"] == "clarify" and meta["route_confidence"] == 0.4


def test_schema_route_answers_from_schema_only(monkeypatch):
    monkeypatch.setattr(agent_service, "json_with_llm", lambda hint, content, **k: {
        "provider": "openai", "model": "m",
        "result": {"summary": "요약", "markdown": "orders 테이블이 있습니다."}})
    run = agent_with(monkeypatch, {"route": "schema_qa", "source": "jev", "clarify": False})
    summary, artifact, meta = run()
    assert summary == "요약"
    assert artifact["widgets"][0]["component"] == "MarkdownBlock"
    assert meta["route"] == "schema_qa"


def test_knowledge_route_says_graph_is_not_connected(monkeypatch):
    run = agent_with(monkeypatch, {"route": "knowledge_qa", "source": "jev", "clarify": False})
    summary, artifact, meta = run()
    assert "아직" in summary
    assert [c["route"] for c in artifact["choices"]] == ["data_query", "schema_qa"]


def test_route_failure_becomes_agent_error(monkeypatch):
    monkeypatch.setattr(agent_service, "_resolve_db_url", lambda *a, **k: ("db", "test", set()))
    monkeypatch.setattr(agent_service, "_schema_text_for_connection", lambda *a, **k: "schema")

    def fail(*a, **k):
        raise router.RouteError("boom")

    monkeypatch.setattr(agent_service, "decide_route", fail)
    with pytest.raises(agent_service.AgentRunError, match="boom"):
        agent_service.run_agent("질문", tenant_id="t", user_id="u")
