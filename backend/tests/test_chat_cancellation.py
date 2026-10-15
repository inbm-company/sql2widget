"""Cancellation uses model/DB substitutes and does not contact external services."""

import asyncio
from threading import Event

import pytest
from fastapi import HTTPException

from app import chat_cancellation as cancellation


class ConnectedRequest:
    async def is_disconnected(self):
        return False


def test_connected_chat_preserves_result_and_failure():
    async def scenario():
        assert await cancellation.run_chat(ConnectedRequest(), lambda: {"answer": "ok"}) == {"answer": "ok"}
        def fail():
            raise ValueError("model failed")
        with pytest.raises(ValueError, match="model failed"):
            await cancellation.run_chat(ConnectedRequest(), fail)
    asyncio.run(scenario())


def test_disconnect_stops_followup_and_does_not_cancel_another_chat():
    started = Event()
    saved = []

    class DisconnectedRequest:
        async def is_disconnected(self):
            return started.is_set()

    @cancellation.cancellation_checkpoint
    def blocked_model():
        started.set()
        # A synchronous provider returns later; this simulates that boundary.
        event = cancellation._cancel_event.get()
        assert event.wait(3), "disconnect was not forwarded to the worker"
        return "late answer"

    def work():
        try:
            answer = blocked_model()
        except Exception:
            saved.append("fallback must not run")
        else:
            saved.append(answer)

    async def scenario():
        cancelled, normal = await asyncio.gather(
            cancellation.run_chat(DisconnectedRequest(), work),
            cancellation.run_chat(ConnectedRequest(), lambda: "independent answer"),
            return_exceptions=True,
        )
        assert isinstance(cancelled, HTTPException)
        assert cancelled.status_code == 499
        assert normal == "independent answer"
        assert saved == []
        # Request-scoped context must not leak to subsequent operations.
        cancellation.check_cancelled()
        assert await cancellation.run_chat(ConnectedRequest(), lambda: "next question") == "next question"
    asyncio.run(scenario())

def test_chat_api_never_saves_answer_after_disconnect(monkeypatch):
    from app import main
    from app.contracts import ChatRequest

    started = Event()
    saved = []
    user = {"id": "user", "tenant_id": "tenant", "role": "admin"}

    class DisconnectedRequest:
        headers = {}

        async def is_disconnected(self):
            return started.is_set()

    monkeypatch.setattr(main.conv_repo, "get_conversation", lambda *a: {
        "id": "conversation", "project_id": "project", "messages": []})
    monkeypatch.setattr(main.conv_repo, "touch_title_from_message", lambda *a: None)

    def save(conversation_id, role, *args, **kwargs):
        saved.append(role)
        return {"id": "message"}
    monkeypatch.setattr(main.conv_repo, "add_message", save)

    def answer(*args, **kwargs):
        started.set()
        assert cancellation._cancel_event.get().wait(3)
        return "late answer", {"type": "answer", "widgets": []}, {}
    monkeypatch.setattr(main, "run_agent", answer)
    if hasattr(main, "embed_text"):
        monkeypatch.setattr(main, "embed_text", lambda *a, **kw: {
            "embedding": None, "provider": "test", "error": None})

    async def scenario():
        with pytest.raises(HTTPException) as error:
            await main.chat(ChatRequest(conversation_id="conversation", message="question"),
                            DisconnectedRequest(), user)
        assert error.value.status_code == 499
        assert saved == ["user"]
    asyncio.run(scenario())
