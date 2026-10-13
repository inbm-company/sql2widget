import pytest

from app.catalog_props import EXTRA_COMPONENTS
from app.widget_props import rows_to_props
from app.widget_queries import widget_definition, load_widget_data
from app import widget_queries


CASES = [
    ("CompareCard", [{"current": 150, "previous": 100}], "delta", 50),
    ("PivotTable", [{"row": "APAC", "column": "A", "value": 2}, {"row": "APAC", "column": "A", "value": 3}], "totals", {"row": "전체 합계", "c0": 5, "total": 5}),
    ("StatusSummary", [{"status": "open", "count": 3}, {"status": "closed", "count": 1}], "total", 4),
    ("EventTimeline", [{"occurred_at": "2026-10-01T00:00:00Z", "title": "A"}, {"occurred_at": "2026-10-02", "title": "B"}], "items", [
        {"occurredAt": "2026-10-02", "title": "B", "description": None}, {"occurredAt": "2026-10-01T00:00:00Z", "title": "A", "description": None}]),
    ("KpiGroup", [{"label": "매출", "value": 0, "unit": "원"}], "items", [{"label": "매출", "value": 0, "unit": "원"}]),
    ("DetailCard", [{"hostname": "server", "owner": None}], "fields", [{"label": "hostname", "value": "server"}, {"label": "owner", "value": None}]),
    ("HorizontalBarChart", [{"label": "A", "value": -2}], "categories", ["A"]),
    ("ComboChart", [{"x": "1월", "bar_value": 200, "line_value": 3}], "points", [{"x": "1월", "bar": 200, "line": 3}]),
    ("BoxPlot", [{"label": "A", "minimum": 1, "q1": 2, "median": 3, "q3": 4, "maximum": 5, "outliers": [9]}], "boxes", [{"label": "A", "minimum": 1, "q1": 2, "median": 3, "q3": 4, "maximum": 5, "outliers": [9]}]),
    ("Treemap", [{"group": "G", "label": "A", "value": 2}], "nodes", [
        {"id": "root", "parentId": None, "label": "전체", "group": "", "value": 0},
        {"id": "g0", "parentId": "root", "label": "G", "group": "G", "value": 0},
        {"id": "n0", "parentId": "g0", "label": "A", "group": "G", "value": 2}]),
]


@pytest.mark.parametrize("component,rows,key,expected", CASES)
def test_new_widgets_convert_sql_and_fetch_without_persisting_results(monkeypatch, component, rows, key, expected):
    assert rows_to_props(component, rows, "Title")[key] == expected
    definition = widget_definition({"component": component, "sql": "SELECT * FROM permitted",
        "query_ref": {"sql": "SELECT * FROM permitted", "connection_id": "db"},
        "props": {"value": 999, "rows": [{"secret": True}], "color": "red", "xLabel": "X", "yLabel": "Y"}})
    assert "rows" not in definition["props"] and "value" not in definition["props"] and "color" not in definition["props"]
    monkeypatch.setattr(widget_queries.connections, "get_connection", lambda *a: {"id": "db"})
    monkeypatch.setattr(widget_queries.connections, "allowed_tables_for_role", lambda *a: {"permitted"})
    monkeypatch.setattr(widget_queries.connections, "connection_url", lambda *a: "customer-db")
    calls = []
    monkeypatch.setattr(widget_queries, "execute_readonly", lambda url, sql, **kwargs: calls.append((url, kwargs)) or rows)
    result = load_widget_data(definition, {"tenant_id": "t", "role": "viewer"})
    assert result["props"][key] == expected
    assert calls == [("customer-db", {"allowed_tables": {"permitted"}})]


@pytest.mark.parametrize("component", sorted(EXTRA_COMPONENTS))
def test_new_widgets_handle_empty_results(component):
    assert isinstance(rows_to_props(component, [], "Empty"), dict)


def test_comparison_zero_reference_and_negative_reference():
    assert rows_to_props("CompareCard", [{"current": 1, "previous": 0}], "Compare")["changeRate"] is None
    assert rows_to_props("CompareCard", [{"current": -5, "previous": -10}], "Compare")["changeRate"] == 50
    with pytest.raises(ValueError, match="single comparison"):
        rows_to_props("CompareCard", [{"current": 1, "previous": 1}] * 2, "Compare")


def test_invalid_statistical_rows_are_not_rendered_as_valid():
    for component, rows in [
        ("StatusSummary", [{"status": "A", "count": -1}]),
        ("BoxPlot", [{"label": "A", "minimum": 1, "q1": 5, "median": 3, "q3": 4, "maximum": 7}]),
        ("BoxPlot", [{"label": "A", "minimum": 1, "q1": 2, "median": 3, "q3": 4, "maximum": 7, "outliers": [3]}]),
        ("Treemap", [{"group": "A", "label": "B", "value": -1}]),
        ("DetailCard", [{"id": 1}, {"id": 2}]),
        ("EventTimeline", [{"occurred_at": "invalid", "title": "A"}]),
    ]:
        with pytest.raises(ValueError): rows_to_props(component, rows, "Invalid")


def test_multiline_keeps_gaps_and_rejects_duplicate_series_positions():
    result = rows_to_props("LineChart", [{"x": "1월", "y": 3, "series": "A"}, {"x": "2월", "y": 5, "series": "B"}], "Line")
    assert result["series"] == [{"name": "A", "points": [{"x": "1월", "y": 3}, {"x": "2월", "y": None}]},
                                {"name": "B", "points": [{"x": "1월", "y": None}, {"x": "2월", "y": 5}]}]
    with pytest.raises(ValueError, match="unique"):
        rows_to_props("LineChart", [{"x": "1月", "y": 3, "series": "A"}] * 2, "Line")


def test_filter_query_results_are_transient_and_static_legacy_chips_are_preserved():
    props = rows_to_props("FilterBar", [{"region": "APAC", "value": 3}], "Filter")
    assert props["rows"] == [{"region": "APAC", "value": 3}]
    assert widget_definition({"component": "FilterBar", "sql": "SELECT * FROM permitted", "props": props})["props"] == {}
    chips = {"component": "FilterBar", "props": {"filters": [{"label": "지역", "value": "APAC"}]}}
    assert widget_definition(chips) == chips
