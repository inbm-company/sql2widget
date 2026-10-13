"""Bind independent SQL result columns to the closed widget data contracts."""

from app.catalog_props import SQL_COLUMNS as CATALOG_COLUMNS
from app.widget_props import SQL_COLUMNS as ANALYTICAL_COLUMNS

COLUMN_ROLES = {
    "KpiStat": ("value", "unit"), "RankList": ("label", "value", "meta"),
    "BarChart": ("label", "value"), "BarTable": ("label", "value"),
    "LineChart": ("x", "y", "series"), "PieChart": ("label", "value"),
    "PieTable": ("label", "value"), "KpiSparkline": ("value", "x", "y", "unit"),
    **ANALYTICAL_COLUMNS, **CATALOG_COLUMNS,
}
COLUMN_ROLES["ScatterChart"] = ("x", "y", "label")
COLUMN_ROLES["CompareCard"] = ("current", "previous", "label", "unit")
COLUMN_ROLES["EventTimeline"] = ("occurred_at", "title", "description")
COLUMN_ROLES["KpiGroup"] = ("label", "value", "unit")
COLUMN_ROLES["BoxPlot"] = (*CATALOG_COLUMNS["BoxPlot"], "outliers")
REQUIRED_ROLES = {component: set(roles) for component, roles in COLUMN_ROLES.items()}
REQUIRED_ROLES.update({"KpiStat": {"value"}, "RankList": {"label", "value"},
    "LineChart": {"x", "y"}, "ScatterChart": {"x", "y"}, "CompareCard": {"current", "previous"},
    "EventTimeline": {"occurred_at", "title"}, "KpiGroup": {"label", "value"},
    "BoxPlot": set(CATALOG_COLUMNS["BoxPlot"]), "KpiSparkline": {"value", "x", "y"}})
RAW_COMPONENTS = {"DataTable", "FilterBar", "DetailCard"}
SCALAR_COMPONENTS = {"KpiStat", "CompareCard", "DetailCard"}
NUMERIC_ROLES = {
    "KpiStat": {"value"}, "RankList": {"value"}, "BarChart": {"value"}, "BarTable": {"value"},
    "LineChart": {"y"}, "PieChart": {"value"}, "PieTable": {"value"}, "KpiSparkline": {"value", "y"},
    "StackedBarChart": {"value"}, "Heatmap": {"value"}, "ScatterChart": {"x", "y"},
    "Histogram": {"bin_start", "bin_end", "count"}, "CompareCard": {"current", "previous"},
    "PivotTable": {"value"}, "StatusSummary": {"count"}, "KpiGroup": {"value"},
    "HorizontalBarChart": {"value"}, "ComboChart": {"bar_value", "line_value"},
    "BoxPlot": {"minimum", "q1", "median", "q3", "maximum"}, "Treemap": {"value"},
}


def validate_binding(component, mapping, columns):
    if not isinstance(mapping, dict):
        raise ValueError("위젯 컬럼 연결 형식이 올바르지 않습니다.")
    if component in RAW_COMPONENTS:
        if mapping:
            raise ValueError(f"{component}은 원래 조회 컬럼을 사용합니다.")
        return {}
    roles = COLUMN_ROLES.get(component)
    if roles is None:
        raise ValueError("위젯 컬럼 연결 형식이 올바르지 않습니다.")
    if not REQUIRED_ROLES[component] <= mapping.keys() or not mapping.keys() <= set(roles):
        raise ValueError(f"{component} 위젯의 컬럼 역할이 계약과 맞지 않습니다.")
    if any(not isinstance(source, str) or source not in columns for source in mapping.values()):
        raise ValueError("조회 결과에 없는 컬럼을 위젯에 연결할 수 없습니다.")
    return {role: mapping[role] for role in roles if role in mapping}


def map_widget_rows(component, rows, mapping):
    if mapping is None:
        return rows  # Existing SQL definitions keep their original alias behavior.
    columns = set(rows[0]) if rows else set(mapping.values()) if isinstance(mapping, dict) else set()
    binding = validate_binding(component, mapping, columns)
    if component in RAW_COMPONENTS:
        return rows
    return [{role: row[source] for role, source in binding.items()} for row in rows]
