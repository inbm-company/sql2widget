from contextlib import contextmanager

from fastapi.testclient import TestClient

from app import db, main
from app.auth import get_current_user
from app.chat_trace import message_meta
from app.repositories import conversations


def test_trace_excludes_raw_errors_credentials_and_reference_sql():
    raw = {
        "route": "data_query", "route_source": "llm_fallback", "route_jev_error": "never-persist",
        "api_key": "never-persist", "provider": "gemini", "model": "m",
        "schema_link": {"source": "full", "reason": "no_matched_tables", "error": "never-persist"},
        "question_retrieval": {"status": "matched", "matches": [
            {"question": "고객 순위", "similarity": 0.9, "plan": {"sql": "never-persist"}}]},
    }
    trace = message_meta(raw)
    assert "never-persist" not in str(trace)
    assert trace["route_fallback"] is True
    assert trace["question_retrieval"] == {
        "status": "matched", "count": 1, "references": [{"question": "고객 순위", "similarity": 0.9}]}
    assert message_meta({"provider": "gemini", "route": "clarify"}) == {"route": "clarify"}




def test_actual_subquestions_route_order_and_replans_are_preserved_in_saved_trace():
    raw = {"route": "general_chat", "steps": [
        {"query": "원래 질문", "route": "general_chat", "expected_route": "general_chat", "plan_revision": 0},
        {"query": "재계획 질문", "route": "general_chat", "expected_route": "general_chat", "plan_revision": 1}]}
    trace = message_meta(raw)
    assert trace["steps"] == raw["steps"]
    raw["steps"][1]["query"] = "변경됨"
    assert trace["steps"][1]["query"] == "재계획 질문"
