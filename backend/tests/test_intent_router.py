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
    args = {"tables": {"orders"}, "forced_route": None,
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


def test_user_choice_skips_every_model(monkeypatch):
    calls = post_json_returning(monkeypatch, jev_body())
    assert decide(forced_route="schema_qa") == {
        "route": "schema_qa", "source": "user_choice", "clarify": False}
    assert calls == []






def test_low_confidence_or_other_asks_the_user(monkeypatch):
    post_json_returning(monkeypatch, jev_body("data_query", 0.3))
    assert decide()["clarify"] is True
    post_json_returning(monkeypatch, jev_body("other", 0.99))
    assert decide()["clarify"] is True








def test_both_models_failing_raises(monkeypatch):
    monkeypatch.setattr(config, "TYPESAFE_API_KEY", "")
    monkeypatch.setattr(router, "json_with_llm", lambda *a, **k: {"result": None, "error": "boom"})
    with pytest.raises(router.RouteError, match="boom"):
        decide()




def agent_with(monkeypatch, decision):
    monkeypatch.setattr(agent_service, "_resolve_db_url", lambda *a, **k: ("db", "test", set()))
    monkeypatch.setattr(agent_service, "_schema_text_for_connection", lambda *a, **k: "schema")
    monkeypatch.setattr(agent_service, "decide_route", lambda *a, **k: decision)
    return lambda: agent_service.run_agent("질문", tenant_id="t", user_id="u")




def test_schema_route_answers_from_schema_only(monkeypatch):
    monkeypatch.setattr(agent_service, "make_plan", lambda *a, **k: {
        "goal": "테이블 구조 설명", "steps": [
            {"route": "schema_qa", "query": "질문", "expect": "테이블 구조 설명"}]})
    monkeypatch.setattr(agent_service, "evaluate", lambda *a, **k: {
        "verdict": "done", "reason": "구조 설명 완료"})
    monkeypatch.setattr(agent_service, "json_with_llm", lambda hint, content, **k: {
        "provider": "openai", "model": "m",
        "result": {"summary": "요약", "markdown": "orders 테이블이 있습니다."}})
    run = agent_with(monkeypatch, {"route": "schema_qa", "source": "jev", "clarify": False})
    summary, artifact, meta = run()
    assert summary == "orders 테이블이 있습니다."
    assert artifact == {"type": "answer", "widgets": []}
    assert meta["route"] == "schema_qa"
