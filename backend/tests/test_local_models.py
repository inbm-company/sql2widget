import httpx
import pytest

from app import local_models


def _fake_get(payload, status=200):
    def get(url, headers=None, timeout=None):
        req = httpx.Request("GET", url)
        return httpx.Response(status, json=payload, request=req)
    return get


def test_list_models_sorted_and_deduped(monkeypatch):
    monkeypatch.setattr(httpx, "get", _fake_get({"data": [{"id": "b"}, {"id": "a"}, {"id": "b"}]}))
    assert local_models.list_models("http://x:11434/v1/") == ["a", "b"]


def test_list_models_rejects_bad_url():
    with pytest.raises(local_models.LocalModelsError):
        local_models.list_models("file:///etc/passwd")


def test_list_models_http_error(monkeypatch):
    monkeypatch.setattr(httpx, "get", _fake_get({}, status=401))
    with pytest.raises(local_models.LocalModelsError, match="401"):
        local_models.list_models("http://x/v1")


def test_list_models_bad_shape(monkeypatch):
    monkeypatch.setattr(httpx, "get", _fake_get({"models": []}))
    with pytest.raises(local_models.LocalModelsError):
        local_models.list_models("http://x/v1")
