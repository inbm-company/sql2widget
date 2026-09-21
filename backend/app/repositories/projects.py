import secrets

from app.db import fetch_all, fetch_one


def _id() -> str:
    return f"prj_{secrets.token_hex(8)}"


def list_projects(tenant_id: str, user_id: str) -> list[dict]:
    return fetch_all(
        """
        SELECT id, title, created_at, updated_at
        FROM projects
        WHERE tenant_id = %s AND user_id = %s
        ORDER BY updated_at DESC, created_at DESC
        """,
        (tenant_id, user_id),
    )


def get_project(project_id: str, tenant_id: str, user_id: str) -> dict | None:
    return fetch_one(
        """
        SELECT id, title, created_at, updated_at
        FROM projects
        WHERE id = %s AND tenant_id = %s AND user_id = %s
        """,
        (project_id, tenant_id, user_id),
    )


def create_project(tenant_id: str, user_id: str, title: str | None = None) -> dict:
    project_id = _id()
    return fetch_one(
        """
        INSERT INTO projects (id, tenant_id, user_id, title)
        VALUES (%s, %s, %s, %s)
        RETURNING id, title, created_at, updated_at
        """,
        (project_id, tenant_id, user_id, (title or "새 프로젝트").strip()[:120] or "새 프로젝트"),
    )


def update_project(
    project_id: str, tenant_id: str, user_id: str, title: str
) -> dict | None:
    final_title = title.strip()[:120] or "새 프로젝트"
    return fetch_one(
        """
        UPDATE projects
        SET title = %s, updated_at = now()
        WHERE id = %s AND tenant_id = %s AND user_id = %s
        RETURNING id, title, created_at, updated_at
        """,
        (final_title, project_id, tenant_id, user_id),
    )
