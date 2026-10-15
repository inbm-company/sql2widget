"""PostgreSQL transaction tests; require the existing local seeded service DB."""

import pytest

from app import db
from app.chat_turns import message_turns
from app.repositories import conversations
from test_projects import project_tree


def no_vectors(monkeypatch):
    calls = []
    if hasattr(conversations, "message_embeddings"):
        monkeypatch.setattr(conversations.message_embeddings, "delete_message_embeddings", lambda tenant, ids:
                            calls.append((tenant, list(ids))))
    return calls


def test_deleting_a_question_keeps_all_answers_and_later_turns(project_tree, monkeypatch):
    project, _, chat, source = project_tree[:4]
    calls = no_vectors(monkeypatch)
    first = conversations.add_message(chat["id"], "assistant", "첫 답변", meta={"reply_to_message_id": source["id"]})
    later = conversations.add_message(chat["id"], "user", "후속 질문")
    later_answer = conversations.add_message(chat["id"], "assistant", "후속 답변", meta={"reply_to_message_id": later["id"]})
    regenerated = conversations.add_message(chat["id"], "assistant", "재생성 답변", meta={
        "reply_to_message_id": source["id"], "response_mode": "regenerate"})
    assert conversations.delete_message(chat["id"], source["id"], "other-tenant", "user_admin") is False
    assert conversations.delete_message(chat["id"], source["id"], "tenant_demo", "user_viewer") is False
    assert conversations.delete_message(chat["id"], source["id"], "tenant_demo", "user_admin") is True
    remaining = conversations.get_conversation(chat["id"], "tenant_demo", "user_admin")
    assert {message["id"] for message in remaining["messages"]} == {
        first["id"], later["id"], later_answer["id"], regenerated["id"]}
    assert conversations.delete_message(chat["id"], source["id"], "tenant_demo", "user_admin") is False
    if calls:
        assert calls == [("tenant_demo", [source["id"]])]
    assert db.fetch_one("SELECT id FROM projects WHERE id = %s", (project["id"],))
    assert db.fetch_one("SELECT id FROM stage_widgets WHERE id = %s", (project_tree[5]["id"],))


def test_deleting_one_answer_keeps_its_question_and_sibling_answers(project_tree, monkeypatch):
    _, _, chat, source = project_tree[:4]
    calls = no_vectors(monkeypatch)
    first = conversations.add_message(chat["id"], "assistant", "첫 답변", meta={"reply_to_message_id": source["id"]})
    second = conversations.add_message(chat["id"], "assistant", "재생성 답변", meta={
        "reply_to_message_id": source["id"], "response_mode": "regenerate"})
    assert conversations.delete_message(chat["id"], second["id"], "tenant_demo", "user_admin")
    remaining = conversations.get_conversation(chat["id"], "tenant_demo", "user_admin")
    assert {message["id"] for message in remaining["messages"]} == {source["id"], first["id"]}
    if calls:
        assert calls == [("tenant_demo", [second["id"]])]


def test_deleting_legacy_question_does_not_reparent_its_retained_answer(project_tree, monkeypatch):
    _, _, chat, previous = project_tree[:4]
    no_vectors(monkeypatch)
    removed = conversations.add_message(chat["id"], "user", "삭제할 질문")
    legacy = conversations.add_message(chat["id"], "assistant", "남길 답변")
    assert conversations.delete_message(chat["id"], removed["id"], "tenant_demo", "user_admin")
    remaining = conversations.get_conversation(chat["id"], "tenant_demo", "user_admin")["messages"]
    retained = next(message for message in remaining if message["id"] == legacy["id"])
    assert retained["meta"]["reply_to_message_id"] == removed["id"]
    turns = message_turns(remaining)
    assert turns[0]["question"]["id"] == previous["id"]
    assert turns[0]["answers"] == []
    assert turns[-1]["question"] is None
    assert turns[-1]["answers"][0]["id"] == legacy["id"]


def test_removed_question_cannot_receive_a_late_assistant_reply(project_tree, monkeypatch):
    _, _, chat, source = project_tree[:4]
    no_vectors(monkeypatch)
    assert conversations.delete_message(chat["id"], source["id"], "tenant_demo", "user_admin")
    with pytest.raises(conversations.MessageDeletedError):
        conversations.add_message(chat["id"], "assistant", "late", meta={"reply_to_message_id": source["id"]})
    assert conversations.get_conversation(chat["id"], "tenant_demo", "user_admin")["messages"] == []


def test_newer_attempt_prevents_late_old_reply_and_clears_pending_on_success(project_tree):
    _, _, chat, source = project_tree[:4]
    assert conversations.mark_response_pending(chat["id"], source["id"], "old-attempt", "regenerate")
    assert conversations.mark_response_pending(chat["id"], source["id"], "new-attempt", "regenerate")
    with pytest.raises(conversations.MessageDeletedError):
        conversations.add_message(chat["id"], "assistant", "old result", meta={
            "reply_to_message_id": source["id"], "response_request_id": "old-attempt"})
    saved = conversations.add_message(chat["id"], "assistant", "new result", meta={
        "reply_to_message_id": source["id"], "response_request_id": "new-attempt"})
    conversation = conversations.get_conversation(chat["id"], "tenant_demo", "user_admin")
    assert conversation["messages"][0]["meta"]["response_pending"] is False
    assert conversation["messages"][-1]["id"] == saved["id"]


def test_vector_cleanup_failure_rolls_back_message_deletion(project_tree, monkeypatch):
    _, _, chat, source = project_tree[:4]
    def fail(*args):
        raise RuntimeError("vector store unavailable")
    monkeypatch.setattr(conversations.message_embeddings, "delete_message_embeddings", fail)
    with pytest.raises(RuntimeError, match="vector store unavailable"):
        conversations.delete_message(chat["id"], source["id"], "tenant_demo", "user_admin")
    assert conversations.get_conversation(chat["id"], "tenant_demo", "user_admin")["messages"][0]["id"] == source["id"]


def test_legacy_pinned_widget_keeps_query_reference_when_only_its_answer_is_deleted(project_tree, monkeypatch):
    from app.repositories import stages
    _, _, chat, source, stage, widget = project_tree[:6]
    no_vectors(monkeypatch)
    answer = conversations.add_message(chat["id"], "assistant", "결과", {
        "artifact_id": "artifact-original", "widgets": [
            {"widget_id": "source-widget", "component": "DataTable", "sql": "SELECT 1 AS value", "props": {}}]},
        meta={"connection_id": "sales", "reply_to_message_id": source["id"]})
    db.execute("UPDATE stage_widgets SET source_artifact_id = %s, source_widget_id = %s, props = %s::jsonb WHERE id = %s",
               ("artifact-original", "source-widget", '{"__sql":"SELECT 1 AS value"}', widget["id"]))
    assert conversations.delete_message(chat["id"], answer["id"], "tenant_demo", "user_admin")
    preserved = stages.get_or_create_stage(project_tree[0]["id"], "tenant_demo", "user_admin")["widgets"][0]
    assert preserved["id"] == widget["id"]
    assert preserved["query_ref"] == {"sql": "SELECT 1 AS value", "connection_id": "sales"}
    assert conversations.get_conversation(chat["id"], "tenant_demo", "user_admin")["messages"][0]["id"] == source["id"]
