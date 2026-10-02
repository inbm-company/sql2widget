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


def test_chat_response_and_reloaded_conversation_keep_the_same_processing_record(monkeypatch):
    trace = {"route": "data_query", "route_source": "jev", "model": "m", "provider": "gemini",
             "schema_link": {"source": "similarity", "tables": ["orders"], "total": 32},
             "question_retrieval": {"status": "matched", "matches": [{"question": "고객별 주문", "similarity": 0.9}]}}
    monkeypatch.setattr(main, "run_agent", lambda *a, **k: ("답변", {"widgets": []}, trace))
    monkeypatch.setattr(main, "embed_text", lambda *a, **k: {"embedding": None, "error": None, "provider": "gemini"})
    monkeypatch.setitem(main.app.dependency_overrides, get_current_user,
                        lambda: {"id": "user_admin", "tenant_id": "tenant_demo", "role": "admin"})
    original = db.get_conn
    with original() as conn:
        conn.execute("SELECT 1")

        @contextmanager
        def transaction():
            with conn.transaction():
                yield conn

        monkeypatch.setattr(db, "get_conn", transaction)
        monkeypatch.setattr(conversations, "get_conn", transaction)
        try:
            chat = conversations.create_conversation("tenant_demo", "user_admin", "prj_default_user_admin", "처리 내역 테스트")
            client = TestClient(main.app)
            response = client.post("/api/chat", json={"conversation_id": chat["id"], "message": "고객별 주문 보여줘"})
            assert response.status_code == 200
            saved = response.json()["assistant_message"]["meta"]
            assert saved == message_meta(trace)
            reloaded = client.get(f"/api/conversations/{chat['id']}").json()
            messages = {item["role"]: item for item in reloaded["messages"]}
            assert messages["user"]["meta"] is None
            assert messages["assistant"]["meta"] == saved
        finally:
            conn.rollback()
