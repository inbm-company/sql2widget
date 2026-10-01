from contextlib import contextmanager
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app import db
from app.auth import get_current_user
from app.db import execute, fetch_one
from app.main import app
from app.repositories import conversations, graph_sources, message_embeddings, stages
from app.repositories import projects as project_repo


def test_update_project():
    project = project_repo.create_project("tenant_demo", "user_admin", "원래 이름")

    try:
        updated = project_repo.update_project(
            project["id"], "tenant_demo", "user_admin", "변경된 프로젝트"
        )
        assert updated["title"] == "변경된 프로젝트"
    finally:
        execute("DELETE FROM projects WHERE id = %s", (project["id"],))


@pytest.fixture
def project_tree(monkeypatch):
    original = db.get_conn
    with original() as conn:
        # Keep a parent transaction open; repository transactions become savepoints.
        conn.execute("SELECT 1")
        @contextmanager
        def transaction():
            with conn.transaction():
                yield conn

        for module in (db, project_repo, conversations, stages, graph_sources):
            monkeypatch.setattr(module, "get_conn", transaction)
        project = project_repo.create_project("tenant_demo", "user_admin", "삭제 테스트")
        other = project_repo.create_project("tenant_demo", "user_admin", "유지 테스트")
        chat = conversations.create_conversation("tenant_demo", "user_admin", project["id"])
        message = conversations.add_message(chat["id"], "user", "테스트 메시지")
        stage = stages.get_or_create_stage(project["id"], "tenant_demo", "user_admin")
        widget = stages.add_widget(stage["id"], {
            "component": "DataTable", "title": "테스트 위젯", "props": {}, "layout": {},
        })
        source = graph_sources.create_source(
            tenant_id="tenant_demo", project_id=project["id"], created_by="user_admin",
            name="보존 소스", files={"note.md": "# 보존 문서"},
        )
        try:
            yield project, other, chat, message, stage, widget, source, original
        finally:
            conn.rollback()


def test_delete_project_cascades_and_preserves_sources(project_tree):
    project, other, chat, message, stage, widget, source, _ = project_tree
    assert project_repo.delete_project(project["id"], "tenant_demo", "user_admin") is True
    for table, record in (
        ("projects", project), ("conversations", chat), ("messages", message),
        ("stages", stage), ("stage_widgets", widget),
    ):
        assert fetch_one(f"SELECT id FROM {table} WHERE id = %s", (record["id"],)) is None
    assert project_repo.get_project(other["id"], "tenant_demo", "user_admin")
    preserved = fetch_one("SELECT * FROM graph_sources WHERE id = %s", (source["id"],))
    assert preserved["project_id"] is None
    assert preserved["path"] == source["path"]
    assert project_repo.delete_project(project["id"], "tenant_demo", "user_admin") is False


def test_delete_project_rejects_other_owner_and_tenant(project_tree):
    project = project_tree[0]
    assert project_repo.delete_project(project["id"], "tenant_demo", "user_viewer") is False
    assert project_repo.delete_project(project["id"], "other_tenant", "user_admin") is False
    assert project_repo.get_project(project["id"], "tenant_demo", "user_admin")


def test_delete_project_during_source_job_is_atomic(project_tree):
    project, _, chat, _, _, _, source, original = project_tree
    with original() as lock_conn:
        with lock_conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (source["id"],))
            with pytest.raises(project_repo.ProjectBusyError):
                project_repo.delete_project(project["id"], "tenant_demo", "user_admin")
    assert project_repo.get_project(project["id"], "tenant_demo", "user_admin")
    assert conversations.get_conversation(chat["id"], "tenant_demo", "user_admin")
    assert project_repo.delete_project(project["id"], "tenant_demo", "user_admin") is True


def test_delete_project_removes_vector_messages(project_tree):
    project, other, chat, message, *_ = project_tree
    with message_embeddings.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO message_embeddings
                (id, tenant_id, conversation_id, message_id, role, content, embedding)
                VALUES (%s,%s,%s,%s,'user','테스트',array_fill(0.1::real, ARRAY[1536])::vector)""",
                (f"me_{uuid4()}", "tenant_demo", chat["id"], message["id"]),
            )
    try:
        assert project_repo.delete_project(project["id"], "tenant_demo", "user_admin") is True
        with message_embeddings.get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM message_embeddings WHERE conversation_id = %s", (chat["id"],))
                assert cur.fetchone() is None
        assert project_repo.get_project(other["id"], "tenant_demo", "user_admin")
    finally:
        message_embeddings.delete_conversation_embeddings("tenant_demo", [chat["id"]])


def test_vector_cleanup_failure_keeps_project_for_retry(project_tree, monkeypatch):
    project, _, chat, *_ = project_tree
    def fail(*args):
        raise RuntimeError("vector store unavailable")
    monkeypatch.setattr(message_embeddings, "delete_conversation_embeddings", fail)
    with pytest.raises(RuntimeError, match="vector store unavailable"):
        project_repo.delete_project(project["id"], "tenant_demo", "user_admin")
    assert project_repo.get_project(project["id"], "tenant_demo", "user_admin")
    assert conversations.get_conversation(chat["id"], "tenant_demo", "user_admin")


@pytest.mark.parametrize("role,status", [("viewer", 403), ("user", 200), ("admin", 200)])
def test_delete_project_api_permission(project_tree, role, status):
    project = project_tree[0]
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "user_admin", "tenant_id": "tenant_demo", "role": role,
    }
    try:
        with TestClient(app) as client:
            response = client.delete(f"/api/projects/{project['id']}")
            assert response.status_code == status
            if status == 200:
                assert response.json() == {"ok": True}
                assert client.delete(f"/api/projects/{project['id']}").status_code == 404
            else:
                assert project_repo.get_project(project["id"], "tenant_demo", "user_admin")
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
