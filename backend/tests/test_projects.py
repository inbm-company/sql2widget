from contextlib import contextmanager
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app import db
from app.auth import get_current_user
from app.db import execute, fetch_one
from app.main import app
from app.repositories import conversations, message_embeddings, stages
from app.repositories import projects as project_repo




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

        for module in (db, project_repo, conversations, stages):
            monkeypatch.setattr(module, "get_conn", transaction)
        project = project_repo.create_project("tenant_demo", "user_admin", "삭제 테스트")
        other = project_repo.create_project("tenant_demo", "user_admin", "유지 테스트")
        chat = conversations.create_conversation("tenant_demo", "user_admin", project["id"])
        message = conversations.add_message(chat["id"], "user", "테스트 메시지")
        stage = stages.get_or_create_stage(project["id"], "tenant_demo", "user_admin")
        widget = stages.add_widget(stage["id"], {
            "component": "DataTable", "title": "테스트 위젯", "props": {}, "layout": {},
        })
        try:
            yield project, other, chat, message, stage, widget, original
        finally:
            conn.rollback()




def test_delete_project_rejects_other_owner_and_tenant(project_tree):
    project = project_tree[0]
    assert project_repo.delete_project(project["id"], "tenant_demo", "user_viewer") is False
    assert project_repo.delete_project(project["id"], "other_tenant", "user_admin") is False
    assert project_repo.get_project(project["id"], "tenant_demo", "user_admin")






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
