import pytest

from app import agent_plan


def test_multiple_questions_keep_full_constraints_even_on_the_same_route():
    question = "조건 " * 200 + "마지막 지역 조건 유지"
    steps = agent_plan._steps([
        {"route": "general_chat", "query": question},
        {"route": "general_chat", "query": "별도 두 번째 요청"}], "전체 요청")
    assert [step["query"] for step in steps] == [question, "별도 두 번째 요청"]


def test_missing_subquestion_is_not_replaced_with_the_entire_request():
    with pytest.raises(agent_plan.PlanError):
        agent_plan._steps([{"route": "general_chat", "query": "첫 질문"},
                           {"route": "general_chat"}], "전체 요청")
