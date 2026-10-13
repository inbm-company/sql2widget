"""Live customer SELECT + temporary Stage storage + widget data API integration."""

import json
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from app import agent_service, db, main
from app.auth import get_current_user
from app.repositories import connections, stages


@pytest.mark.parametrize("component,sql,data_key", [
    ("KpiStat", "SELECT clock_timestamp()::text AS value FROM monthly_sales LIMIT 1", "value"),
    ("DataTable", "SELECT month, revenue FROM monthly_sales ORDER BY month LIMIT 3", "rows"),
    ("BarChart", "SELECT month, SUM(revenue) AS value FROM monthly_sales GROUP BY month ORDER BY month", "categories"),
    ("StackedBarChart", "SELECT month AS category, region_id AS series, SUM(revenue) AS value FROM monthly_sales GROUP BY month, region_id", "series"),
    ("Heatmap", "SELECT region_id AS x, product_id AS y, SUM(revenue) AS value FROM monthly_sales GROUP BY region_id, product_id", "cells"),
    ("ScatterChart", "SELECT units AS x, revenue AS y FROM monthly_sales LIMIT 5", "points"),
    ("Histogram", "SELECT FLOOR(units / 100.0) * 100 AS bin_start, FLOOR(units / 100.0) * 100 + 100 AS bin_end, COUNT(*) AS count FROM monthly_sales GROUP BY FLOOR(units / 100.0) ORDER BY bin_start", "bins"),
])
def test_live_query_definitions_store_no_results_and_fetch_under_viewer_permissions(monkeypatch, component, sql, data_key):
    user = {"id": "user_admin", "tenant_id": "tenant_demo", "role": "viewer"}
    connection = connections.get_connection("dbconn_global", user["tenant_id"])
    allowed = connections.allowed_tables_for_role(user["tenant_id"], connection["id"], user["role"])
    monkeypatch.setattr(agent_service, "get_document_provider", lambda: type("Provider", (), {"search": lambda *a, **k: []})())
    _, artifact = agent_service._materialize_plan({"widgets": [{"component": component, "title": "검증", "sql": sql}]},
        db_url=connections.connection_url(connection), allowed_tables=allowed, message="조회", connection_id=connection["id"])
    definition = artifact["widgets"][0]
    assert data_key not in definition["props"]

    # No customer writes, and no fixtures left in the real service tables.
    with db.get_conn() as conn:
        conn.execute("""CREATE TEMP TABLE stages (id text PRIMARY KEY, updated_at timestamptz) ON COMMIT DROP""")
        conn.execute("""CREATE TEMP TABLE stage_widgets (
            id text PRIMARY KEY, stage_id text, source_widget_id text, source_artifact_id text,
            component text, title text, props jsonb, layout_i text, layout_x int, layout_y int,
            layout_w int, layout_h int) ON COMMIT DROP""")

        @contextmanager
        def transaction():
            with conn.transaction():
                yield conn

        monkeypatch.setattr(stages, "get_conn", transaction)
        added = stages.add_widget("test-stage", {**definition, "layout": {"i": "test", "x": 0, "y": 0, "w": 4, "h": 4}})
        stored = conn.execute("SELECT props FROM stage_widgets WHERE id = %s", (added["id"],)).fetchone()["props"]
        assert data_key not in stored
        assert stored["__query_ref"]["connection_id"] == "dbconn_global"
        assert "rows" not in stored and "value" not in stored

        monkeypatch.setitem(main.app.dependency_overrides, get_current_user, lambda: user)
        monkeypatch.setattr(main.stage_repo, "get_or_create_stage", lambda *a: {"widgets": [added]})
        monkeypatch.setattr(main.conv_repo, "get_conversation", lambda *a: {"messages": [{
            "role": "assistant", "artifact": artifact, "meta": {"connection_id": connection["id"]}}]})
        with TestClient(main.app) as client:
            chat = client.get(f"/api/conversations/test/widgets/{definition['widget_id']}/data")
            stage = client.get(f"/api/projects/test/stage/widgets/{added['id']}/data")
        assert chat.status_code == stage.status_code == 200
        assert chat.json()["props"][data_key]
        assert stage.json()["props"][data_key]
        if component == "KpiStat":
            assert chat.json()["props"]["value"] != stage.json()["props"]["value"]
        else:
            assert chat.json() == stage.json()
        json.dumps(stage.json())
