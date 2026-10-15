"""Scripted planning and answers: no real model, SQL or database calls."""

from copy import deepcopy

import pytest

from app import agent_plan, agent_service as svc
from app.chat_trace import message_meta


@pytest.fixture
def world(monkeypatch):
    state = {"steps": [
        {"route": "schema_qa", "query": "주문 테이블 구조는?", "expect": "구조 설명"},
        {"route": "general_chat", "query": "정규화는 무슨 개념이야?", "expect": "개념 설명"},
        {"route": "schema_qa", "query": "앞서 본 테이블의 키 관계는?", "expect": "키 설명"}],
        "answers": [], "decisions": [], "evaluation": {"met": True, "reason": "세 요청 완료"}}
    monkeypatch.setattr(svc, "_resolve_db_url", lambda *a, **k: ("unused", "sales", {"orders"}))
    monkeypatch.setattr(svc, "_schema_text_for_connection", lambda *a, **k: "orders(id integer)")

    def llm(hint, content, **kwargs):
        if hint == agent_plan.PLAN_HINT:
            return {"result": {"goal": "세 질문 답변", "steps": deepcopy(state["steps"])}}
        return {"result": state["evaluation"]}
    monkeypatch.setattr(agent_plan, "json_with_llm", llm)

    def route(query, **kwargs):
        state["decisions"].append((query, deepcopy(kwargs)))
        chosen = "clarify" if state.get("clarify") == query else kwargs["expected_route"]
        return {"route": chosen, "source": "jev", "confidence": 0.9, "clarify": chosen == "clarify"}
    monkeypatch.setattr(svc, "decide_route", route)

    def answer(query, *args, **kwargs):
        state["answers"].append((query, deepcopy(kwargs.get("history"))))
        if state.get("fail") == query:
            raise svc.AgentRunError("model failed")
        return "답변:" + query, {"type": "answer", "widgets": []}, args[-1]
    monkeypatch.setattr(svc, "_answer_general", answer)
    monkeypatch.setattr(svc, "_answer_schema", answer)
    return state


def run():
    return svc.run_agent("세 질문을 차례로 처리해 줘", tenant_id="tenant", user_id="user", connection_id="sales")


def test_subquestions_and_repeated_routes_survive_execution_and_persistence(world):
    _, _, meta = run()
    trace = message_meta(meta)
    assert [step["query"] for step in trace["steps"]] == [step["query"] for step in world["steps"]]
    assert [step["route"] for step in trace["steps"]] == ["schema_qa", "general_chat", "schema_qa"]
    assert [step["route_source"] for step in trace["steps"]] == ["jev"] * 3
    assert [step["verdict"] for step in trace["steps"]] == ["next", "next", "done"]
    history = world["answers"][2][1]
    assert [entry["content"] for entry in history if entry["role"] == "assistant"] == [
        "답변:" + world["steps"][0]["query"], "답변:" + world["steps"][1]["query"]]


def test_partial_failure_keeps_the_question_and_actual_chosen_route(world):
    world["fail"] = world["steps"][1]["query"]
    _, _, meta = run()
    assert meta["loop_stop"] == "incomplete"
    assert len(meta["steps"]) == 2
    assert meta["steps"][1]["query"] == world["fail"]
    assert meta["steps"][1]["route"] == "general_chat"
    assert meta["steps"][1]["status"] == "error"


def test_clarification_records_subquestion_without_running_it(world):
    world["clarify"] = world["steps"][1]["query"]
    _, _, meta = run()
    assert meta["loop_stop"] == "clarify"
    assert meta["steps"][-1]["query"] == world["clarify"]
    assert meta["steps"][-1]["route"] == "clarify"
    assert meta["steps"][-1]["expected_route"] == "general_chat"
    assert len(world["answers"]) == 1


def test_replanned_question_stays_attached_to_its_own_execution(world, monkeypatch):
    world["steps"] = world["steps"][:1]
    extra = {"route": "general_chat", "query": "추가 개념 설명", "expect": "개념 답변"}
    monkeypatch.setattr(svc, "evaluate", lambda plan, done, *a, **k:
        {"verdict": "replan", "reason": "설명 보완", "steps": [extra]}
        if len(done) == 1 else {"verdict": "done", "reason": "완료"})
    _, _, meta = run()
    assert [(step["query"], step["plan_revision"]) for step in meta["steps"]] == [
        ("세 질문을 차례로 처리해 줘", 0), (extra["query"], 1)]
