"""Chat actions with in-memory messages and substituted model/database work."""

from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from app import main
from app.auth import get_current_user
from app.chat_turns import context_messages, message_turns, prepare_response
from app.contracts import ChatRequest


def question(id, content):
    return {"id": id, "role": "user", "content": content, "meta": {
        "connection_id": "sales", "requested_route": "general_chat"}}


def answer(id, parent, content, mode=None):
    return {"id": id, "role": "assistant", "content": content,
            "artifact": {"type": "answer", "widgets": []}, "meta": {
                "reply_to_message_id": parent, "connection_id": "sales", "response_mode": mode}}


@pytest.fixture
def world(monkeypatch):
    state = {"messages": [question("q1", "첫 질문"), answer("a1", "q1", "기존 답변"),
                           question("q2", "다음 질문"), answer("a2", "q2", "미래 답변")], "calls": []}
    user = {"id": "owner", "tenant_id": "tenant", "role": "admin"}
    monkeypatch.setitem(main.app.dependency_overrides, get_current_user, lambda: user)
    monkeypatch.setattr(main.conv_repo, "get_conversation", lambda cid, *a:
        {"id": cid, "project_id": "project", "messages": deepcopy(state["messages"])} if cid == "chat" else None)
    monkeypatch.setattr(main.conv_repo, "touch_title_from_message", lambda *a: None)
    monkeypatch.setattr(main.conv_repo, "mark_response_pending", lambda *a: True)

    def save(cid, role, content, artifact, meta=None):
        entry = {"id": "saved-" + str(len(state["messages"])), "role": role,
                 "content": content, "artifact": artifact, "meta": meta}
        state["messages"].append(entry)
        return deepcopy(entry)
    monkeypatch.setattr(main.conv_repo, "add_message", save)

    def agent(message, **kwargs):
        state["calls"].append((message, kwargs))
        return "새 답변", {"type": "answer", "widgets": []}, {
            "route": "general_chat", "route_source": "user_choice", "connection_id": "sales"}
    monkeypatch.setattr(main, "run_agent", agent)
    if hasattr(main, "embed_text"):
        monkeypatch.setattr(main, "embed_text", lambda *a, **k: {
            "embedding": None, "provider": "test", "error": None})
    # Avoid lifespan startup: this fixture deliberately substitutes every DB/model boundary.
    client = TestClient(main.app)
    try:
        yield client, state, user
    finally:
        client.close()


def test_regenerate_reuses_original_question_and_excludes_its_answers_and_future(world):
    client, state, _ = world
    result = client.post("/api/chat", json={"conversation_id": "chat", "message": "tampered client text",
        "reply_to_message_id": "q1", "response_mode": "regenerate"})
    assert result.status_code == 200, result.text
    assert state["calls"][0][0] == "첫 질문"
    assert len([m for m in state["messages"] if m["role"] == "user"]) == 2
    body = result.json()
    assert body["assistant_message"]["meta"]["reply_to_message_id"] == "q1"
    assert body["assistant_message"]["meta"]["response_mode"] == "regenerate"
    assert state["messages"][1]["content"] == "기존 답변"
    kwargs = state["calls"][0][1]
    history = kwargs.get("messages") if "messages" in kwargs else kwargs["flow"]["history"]
    assert history == []


def test_continue_uses_saved_results_without_duplicating_the_user_message(world):
    client, state, _ = world
    result = client.post("/api/chat", json={"conversation_id": "chat", "message": "ignored",
        "reply_to_message_id": "q1", "response_mode": "continue"})
    assert result.status_code == 200, result.text
    message, kwargs = state["calls"][0]
    assert "첫 질문" in message and "반복하지 말고" in message
    history = kwargs.get("messages") if "messages" in kwargs else kwargs["flow"]["history"]
    assert [entry["content"] for entry in history] == ["첫 질문", "기존 답변"]
    assert "미래 답변" not in str(history)
    assert len([m for m in state["messages"] if m["role"] == "user"]) == 2


@pytest.mark.parametrize("target", ["missing", "a1", "other-owner-question"])
def test_invalid_or_non_user_sources_do_not_run_a_model(world, target):
    client, state, _ = world
    response = client.post("/api/chat", json={"conversation_id": "chat", "message": "q",
        "reply_to_message_id": target, "response_mode": "regenerate"})
    assert response.status_code == 404
    assert state["calls"] == []
    assert len(state["messages"]) == 4


def test_mode_and_source_must_be_supplied_together(world):
    client, state, _ = world
    response = client.post("/api/chat", json={"conversation_id": "chat", "message": "q", "response_mode": "regenerate"})
    assert response.status_code == 400
    assert state["calls"] == []


def test_regeneration_context_keeps_only_active_answer_and_its_continuations():
    messages = [question("q", "질문"), answer("old", "q", "폐기된 대안"),
                answer("new", "q", "새 결과", "regenerate"), answer("more", "q", "이어진 결과", "continue")]
    assert [entry["content"] for entry in context_messages(messages)] == ["질문", "새 결과", "이어진 결과"]
    assert len(message_turns(messages)[0]["answers"]) == 3


def test_delete_endpoint_passes_owned_scope_and_never_executes_for_viewer(world, monkeypatch):
    client, _, user = world
    calls = []
    monkeypatch.setattr(main.conv_repo, "delete_message", lambda *args: calls.append(args) or True)
    assert client.delete("/api/conversations/chat/messages/q1").status_code == 200
    assert calls == [("chat", "q1", "tenant", "owner")]
    assert client.delete("/api/conversations/chat/messages/a1").status_code == 200
    assert calls[-1] == ("chat", "a1", "tenant", "owner")
    user["role"] = "viewer"
    assert client.delete("/api/conversations/chat/messages/q1").status_code == 403
    assert len(calls) == 2


def test_delete_missing_or_foreign_message_is_404(world, monkeypatch):
    client, _, _ = world
    monkeypatch.setattr(main.conv_repo, "delete_message", lambda *a: False)
    assert client.delete("/api/conversations/chat/messages/q1").status_code == 404


def test_legacy_answers_stay_in_their_question_and_later_regeneration_links_back():
    first, second = question("q1", "同じ"), question("q2", "同じ")
    legacy = {"id": "legacy", "role": "assistant", "content": "old"}
    turns = message_turns([first, legacy, second, answer("a2", "q2", "second"),
                           answer("r1", "q1", "regenerated", "regenerate")])
    assert [[m["id"] for m in turn["answers"]] for turn in turns] == [["legacy", "r1"], ["a2"]]
