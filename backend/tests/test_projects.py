from app.db import execute
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
