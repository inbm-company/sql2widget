import pytest
from fastapi.testclient import TestClient
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt
from app import auth, config, graph_backend, intent_router
from app.main import app


def test_foreign_application_token_is_rejected_before_db_lookup(monkeypatch):
    token=jwt.encode({"sub":"user_admin","type":"access","iss":"doc2graph"},config.APP_SECRET,algorithm="HS256")
    monkeypatch.setattr(auth,"fetch_one",lambda *a,**k:pytest.fail("foreign token must not read DB"))
    with pytest.raises(Exception) as error:
        auth.get_current_user(HTTPAuthorizationCredentials(scheme="Bearer",credentials=token))
    assert error.value.status_code==401
