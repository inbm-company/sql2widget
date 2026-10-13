import json
from contextlib import contextmanager
from decimal import Decimal

import pytest

from app import agent_service, config, question_similarity
from app.agent import sanitize_artifact
from app.contracts import QuestionIn
from app.repositories import stages
from app.widget_props import ANALYTICAL_COMPONENTS, analytical_rows_to_props


CASES = [
    ("StackedBarChart", [{"category": "서울", "series": "A", "value": Decimal("2.5")},
                         {"category": "부산", "series": "B", "value": -1},
                         {"category": "서울", "series": "A", "value": 1}],
     {"categories": ["서울", "부산"], "series": [{"name": "A", "data": [3.5, 0]}, {"name": "B", "data": [0, -1]}]}),
    ("Heatmap", [{"x": "서울", "y": "상품 A", "value": 0}, {"x": "서울", "y": "상품 A", "value": 2}],
     {"cells": [{"x": "서울", "y": "상품 A", "value": 2}]}),
    ("ScatterChart", [{"x": "1.25", "y": -2, "label": "A"}, {"x": 1.25, "y": -2}],
     {"points": [{"x": 1.25, "y": -2, "label": "A"}, {"x": 1.25, "y": -2}]}),
    ("Histogram", [{"bin_start": 10, "bin_end": 20, "count": 0},
                   {"bin_start": 0, "bin_end": 10, "count": 2},
                   {"bin_start": 0, "bin_end": 10, "count": 3}],
     {"bins": [{"start": 0, "end": 10, "count": 5}, {"start": 10, "end": 20, "count": 0}]}),
]


@pytest.mark.parametrize("component,rows,expected", CASES)
def test_sql_rows_build_closed_json_props(component, rows, expected):
    assert agent_service.rows_to_props(component, rows, "테스트") == expected
    assert json.loads(json.dumps(expected)) == expected
    assert component in config.ALLOWED_COMPONENTS
    assert component in question_similarity.SQL_COMPONENTS
    item = QuestionIn.model_validate({"question": "조회", "plan": {"widgets": [
        {"component": component, "sql": "SELECT * FROM allowed_table", "title": "조회"}]}})
    question_similarity._validate_question(item, {"allowed_table"})


@pytest.mark.parametrize("component,key", [("StackedBarChart", "categories"), ("Heatmap", "cells"),
                                          ("ScatterChart", "points"), ("Histogram", "bins")])
def test_empty_sql_results_have_renderable_props(component, key):
    props = analytical_rows_to_props(component, [])
    assert props[key] == []


@pytest.mark.parametrize("component", sorted(ANALYTICAL_COMPONENTS))
def test_missing_aliases_raise_instead_of_guessing(component):
    with pytest.raises(ValueError, match="SQL requires columns"):
        analytical_rows_to_props(component, [{"unknown": 1}])


@pytest.mark.parametrize("value", ["bad", float("nan"), float("inf"), True])
def test_invalid_numeric_values_are_rejected(value):
    with pytest.raises(ValueError, match="finite number"):
        analytical_rows_to_props("ScatterChart", [{"x": value, "y": 1}])


def test_null_observations_are_omitted_without_becoming_zero():
    assert analytical_rows_to_props("ScatterChart", [{"x": None, "y": 3}]) == {"points": []}
    assert analytical_rows_to_props("Heatmap", [{"x": "A", "y": "B", "value": None}]) == {"cells": []}


@pytest.mark.parametrize("rows", [
    [{"bin_start": 0, "bin_end": 0, "count": 1}],
    [{"bin_start": 2, "bin_end": 1, "count": 1}],
    [{"bin_start": 0, "bin_end": 1, "count": -1}],
    [{"bin_start": 0, "bin_end": 1, "count": 0.5}],
    [{"bin_start": 0, "bin_end": 2, "count": 1}, {"bin_start": 1, "bin_end": 3, "count": 1}],
])
def test_histogram_rejects_invalid_or_overlapping_bins(rows):
    with pytest.raises(ValueError, match="Histogram"):
        analytical_rows_to_props("Histogram", rows)


@pytest.mark.parametrize("component,rows,expected", CASES)
def test_sql_artifact_and_stage_json_roundtrip(monkeypatch, component, rows, expected):
    calls = []
    monkeypatch.setattr(agent_service, "execute_readonly", lambda url, sql, **kwargs: calls.append(kwargs) or rows)
    monkeypatch.setattr(agent_service, "get_document_provider", lambda: type("Provider", (), {"search": lambda *a, **k: []})())
    sql = "SELECT * FROM allowed_table"
    _, artifact = agent_service._materialize_plan({"widgets": [{"component": component, "sql": sql,
        "props": {"xLabel": "기준", "yLabel": "수치", "cells": [{"fake": True}]}}]},
        db_url="test-only", allowed_tables={"allowed_table"}, message="조회")
    widget = sanitize_artifact(artifact)["widgets"][0]
    assert widget["component"] == component and widget["sql"] == sql
    assert widget["props"] == {"xLabel": "기준", "yLabel": "수치", **expected}
    assert calls == [{"allowed_tables": {"allowed_table"}}]

    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, query, params):
            if "INSERT INTO stage_widgets" in query:
                self.row = dict(zip(("id", "stage_id", "source_widget_id", "source_artifact_id", "component", "title", "props",
                                     "layout_i", "layout_x", "layout_y", "layout_w", "layout_h"), params))
                self.row["props"] = json.loads(self.row["props"])
        def fetchone(self): return self.row

    @contextmanager
    def connection():
        yield type("Connection", (), {"cursor": lambda self: Cursor()})()

    monkeypatch.setattr(stages, "get_conn", connection)
    payload = {**widget, "layout": {"i": "test", "x": 0, "y": 0, "w": 4, "h": 4}}
    added = stages.add_widget("test-stage", payload)
    assert added["component"] == component and added["props"] == widget["props"]
    replaced = stages.replace_stage_widgets("test-stage", [{**payload, "id": added["id"]}])
    assert replaced[0]["props"] == added["props"]
