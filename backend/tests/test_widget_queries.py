"""Query definitions contain no results; each read checks ownership and permissions."""

import json

import pytest
from fastapi.testclient import TestClient

from app import agent_service, main, widget_queries
from app.catalog_props import DISPLAY_KEYS
from app.auth import get_current_user
from app.query import validate_readonly_select
from app.repositories import conversations, stages


SQL = "SELECT name, value FROM orders"
USER = {"id": "owner", "tenant_id": "tenant", "role": "viewer"}


def widget(component="BarChart", **extra):
    return {"widget_id": "chat-widget", "id": "stage-widget", "component": component,
            "title": "주문", "sql": SQL, "query_ref": {"sql": SQL, "connection_id": "sales"},
            "props": {}, **extra}


@pytest.mark.parametrize("component", sorted(widget_queries.SQL_COMPONENTS))
def test_sql_widgets_discard_embedded_data_and_keep_query_identity(component):
    data = {"rows": [{"secret": "old-result"}], "categories": ["old-result"], "series": [],
            "value": 999, "points": [], "cells": [], "bins": [], "xLabel": "기준", "yLabel": "금액"}
    definition = widget_queries.widget_definition(widget(component, props=data))
    assert "old-result" not in json.dumps(definition)
    assert "value" not in definition["props"]
    assert definition["query_ref"]["connection_id"] == "sales"
    expected = {key: data[key] for key in DISPLAY_KEYS.get(component, ()) if key in data}
    assert definition["props"] == expected
    assert "__query_ref" in widget_queries.stored_widget_props(definition)






def test_generation_rejects_data_without_sql_instead_of_saving_invented_values():
    with pytest.raises(Exception, match="require a read-only SQL"):
        agent_service._materialize_plan({"widgets": [{"component": "KpiStat", "props": {"value": 42}}]},
                                       db_url="unused", allowed_tables={"orders"}, message="주문 수")


@pytest.fixture
def data_api(monkeypatch):
    calls = []
    monkeypatch.setitem(main.app.dependency_overrides, get_current_user, lambda: USER)
    monkeypatch.setattr(main.conv_repo, "get_conversation", lambda *a: {"messages": [
        {"role": "assistant", "artifact": {"widgets": [widget()]}, "meta": {"connection_id": "sales"}}]})
    monkeypatch.setattr(main.stage_repo, "get_or_create_stage", lambda *a: {"id": "stage", "widgets": [widget()]})
    monkeypatch.setattr(widget_queries.connections, "get_connection", lambda conn, tenant:
        calls.append(("connection", conn, tenant)) or {"id": conn})
    monkeypatch.setattr(widget_queries.connections, "connection_url", lambda *a: "customer-only")
    monkeypatch.setattr(widget_queries.connections, "allowed_tables_for_role", lambda tenant, conn, role:
        calls.append(("permission", tenant, conn, role)) or {"orders"})

    def execute(url, sql, **settings):
        validate_readonly_select(sql, settings["allowed_tables"])
        calls.append(("query", url, sql, settings))
        return [{"name": "고객 A", "value": sum(item[0] == "query" for item in calls)}]

    monkeypatch.setattr(widget_queries, "execute_readonly", execute)
    with TestClient(main.app) as client:
        yield client, calls


@pytest.mark.parametrize("url", ["/api/conversations/chat/widgets/chat-widget/data",
                                 "/api/projects/project/stage/widgets/stage-widget/data"])
def test_widget_reads_current_data_with_current_viewer_permissions(data_api, url):
    client, calls = data_api
    first = client.get(url)
    second = client.get(url + "?connection_id=other&sql=DELETE")
    assert first.status_code == second.status_code == 200
    assert first.headers["cache-control"] == "no-store"
    assert first.json()["props"]["series"][0]["data"] == [1]
    assert second.json()["props"]["series"][0]["data"] == [2]
    assert ("connection", "sales", "tenant") in calls
    assert ("permission", "tenant", "sales", "viewer") in calls
    assert all(item[2] == SQL for item in calls if item[0] == "query")


@pytest.mark.parametrize("target,url", [("get_conversation", "/api/conversations/foreign/widgets/chat-widget/data"),
                                       ("get_or_create_stage", "/api/projects/foreign/stage/widgets/stage-widget/data")])
def test_data_api_checks_owner_before_customer_db(data_api, monkeypatch, target, url):
    client, calls = data_api
    lookups = []
    repo = main.conv_repo if target == "get_conversation" else main.stage_repo
    monkeypatch.setattr(repo, target, lambda *a: lookups.append(a) or None)
    assert client.get(url).status_code == 404
    assert lookups == [("foreign", "tenant", "owner")]
    assert calls == []




def test_permission_removal_blocks_refresh_without_demo_fallback(data_api, monkeypatch):
    client, calls = data_api
    monkeypatch.setattr(widget_queries.connections, "allowed_tables_for_role", lambda *a: set())
    assert client.get("/api/projects/project/stage/widgets/stage-widget/data").status_code == 403
    assert not any(item[0] == "query" for item in calls)


@pytest.mark.parametrize("sql", ["DELETE FROM orders", "SELECT * FROM forbidden", "SELECT 1; SELECT 2"])
def test_saved_queries_still_pass_readonly_and_table_validation(data_api, monkeypatch, sql):
    client, calls = data_api
    bad = widget(query_ref={"connection_id": "sales", "sql": sql})
    monkeypatch.setattr(main.stage_repo, "get_or_create_stage", lambda *a: {"widgets": [bad]})
    assert client.get("/api/projects/project/stage/widgets/stage-widget/data").status_code == 400
    assert not any(item[0] == "query" for item in calls)


def test_db_failure_is_local_to_widget_and_never_exposes_credentials(data_api, monkeypatch):
    client, _ = data_api
    def fail(*a, **k):
        raise RuntimeError("postgresql://user:do-not-expose@db")
    monkeypatch.setattr(widget_queries, "execute_readonly", fail)
    response = client.get("/api/projects/project/stage/widgets/stage-widget/data")
    assert response.status_code == 502
    assert "do-not-expose" not in response.text








