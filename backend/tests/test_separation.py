import pytest
from fastapi.testclient import TestClient
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt
from app import auth, config, graph_backend, intent_router
from app.main import app

def test_db_only_contract_and_optional_graph(monkeypatch):
    paths={r.path for r in app.routes}
    assert not any("graph-sources" in p or "/graph" in p for p in paths)
    assert set(intent_router.ANSWER_ROUTES)=={"data_query","schema_qa"}
    monkeypatch.setenv("GRAPH_ENABLED","false")
    monkeypatch.setattr(graph_backend.GraphDatabase,"driver",lambda *a,**k: pytest.fail("must not connect"))
    graph_backend.close_graph_driver()
    with pytest.raises(graph_backend.GraphError,match="사용하지"):
        graph_backend.graph_driver()
    with TestClient(app) as c:
        assert c.get("/api/health").status_code==200
        assert c.post("/api/chat",json={"conversation_id":"c","message":"m","route":"knowledge_qa"}).status_code in (401,422)

def test_foreign_application_token_is_rejected_before_db_lookup(monkeypatch):
    token=jwt.encode({"sub":"user_admin","type":"access","iss":"doc2graph"},config.APP_SECRET,algorithm="HS256")
    monkeypatch.setattr(auth,"fetch_one",lambda *a,**k:pytest.fail("foreign token must not read DB"))
    with pytest.raises(Exception) as error:
        auth.get_current_user(HTTPAuthorizationCredentials(scheme="Bearer",credentials=token))
    assert error.value.status_code==401
