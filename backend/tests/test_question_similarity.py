import json

import pytest
from fastapi.testclient import TestClient

from app import agent_service, llm, main, question_similarity as service
from app.providers import transport
from app.contracts import QuestionIn


def question_item(sql="SELECT count(*) AS value FROM orders"):
    return QuestionIn.model_validate({
        "question": "주문 건수를 보여줘",
        "plan": {"widgets": [{"component": "KpiStat", "title": "주문 수", "sql": sql}]},
    })


@pytest.fixture
def context():
    tables = [
        {"schema": "public", "name": name, "columns": [
            {"name": "id", "type": "integer", "primary_key": True, "nullable": False},
            {"name": "created_at", "type": "timestamp with time zone", "primary_key": False, "nullable": True},
            {"name": "status", "type": "text", "primary_key": False, "nullable": True},
        ]}
        for name in ("orders", "customers", "products", "payments", "returns")
    ]
    return {"row": {}, "table_names": {x["name"] for x in tables},
            "schema_text": "all tables", "metadata": {"tables": tables, "foreign_keys": []},
            "database_info": {"connection_id": "db-a", "database_name": "sales"}}


@pytest.fixture
def embedding(monkeypatch):
    monkeypatch.setattr(service.config, "CHAT_EMBEDDING_DIM", 3)
    result = {"embedding": [1.0, 0.0, 0.0], "provider": "openai", "model": "model-a"}
    monkeypatch.setattr(llm, "embed_text", lambda *args, **kwargs: result)
    return result




def ai_question(table):
    return QuestionIn.model_validate({
        "question": f"{table} 현황을 알려줘",
        "plan": {"widgets": [{"component": "KpiStat", "title": "현황",
                              "sql": f'SELECT count(*) AS value FROM "{table}"'}]},
    }).model_dump()








def test_missing_role_permission_cannot_retrieve_catalog(monkeypatch):
    monkeypatch.setattr(service.connections, "allowed_tables_for_role", lambda *args: set())
    monkeypatch.setattr(service, "connection_context", lambda *args: pytest.fail("No permission"))
    result = service.search_questions("주문 수", tenant_id="t", connection_id="c",
        allowed_tables={"orders"}, user_role="viewer", llm_settings={})
    assert result == {"status": "no_permissions", "matches": []}


















@pytest.fixture
def client():
    main.app.dependency_overrides[main.get_current_user] = lambda: {"id": "u", "tenant_id": "t", "role": "user"}
    with TestClient(main.app) as client:
        yield client
    main.app.dependency_overrides.clear()


def test_non_admin_cannot_seed(client, monkeypatch):
    monkeypatch.setattr(service, "connection_context", lambda *args: pytest.fail("Read before authorization"))
    assert client.post("/api/database-connections/db/questions/seed", json={}).status_code == 403
    # No manual-register route exists at this path anymore; only GET (listing) is defined,
    # so POST correctly reports 405 rather than 404.
    assert client.post("/api/database-connections/db/questions", json=question_item().model_dump()).status_code == 405




def test_other_tenant_connection_is_not_found(client, monkeypatch):
    monkeypatch.setattr(service.connections, "get_connection", lambda *args: None)
    response = client.post("/api/database-connections/other-db/questions/search", json={"question": "주문 수"})
    assert response.status_code == 404


@pytest.fixture
def admin_client():
    main.app.dependency_overrides[main.get_current_user] = lambda: {"id": "u", "tenant_id": "t", "role": "admin"}
    with TestClient(main.app) as client:
        yield client
    main.app.dependency_overrides.clear()






