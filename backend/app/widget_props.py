"""Closed SQL result contracts for the additional analytical widgets."""

import math


ANALYTICAL_COMPONENTS = frozenset({"StackedBarChart", "Heatmap", "ScatterChart", "Histogram"})
SQL_COLUMNS = {
    "StackedBarChart": ("category", "series", "value"),
    "Heatmap": ("x", "y", "value"),
    "ScatterChart": ("x", "y"),
    "Histogram": ("bin_start", "bin_end", "count"),
}


def _number(value, column):
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError(f"Widget column {column} must be a finite number") from None
    if isinstance(value, bool) or not math.isfinite(number):
        raise ValueError(f"Widget column {column} must be a finite number")
    return number


def analytical_rows_to_props(component, rows):
    required = SQL_COLUMNS[component]
    for row in rows:
        missing = [key for key in required if key not in row]
        if missing:
            raise ValueError(f"{component} SQL requires columns: {', '.join(required)}")

    if component == "StackedBarChart":
        categories, series, values = {}, {}, {}
        for row in rows:
            value = _number(row["value"], "value")
            if row["category"] is None or row["series"] is None or value is None:
                continue
            category, name = str(row["category"]), str(row["series"])
            categories.setdefault(category, len(categories))
            series.setdefault(name, None)
            key = (category, name)
            values[key] = _number(values.get(key, 0) + value, "value")
        return {
            "categories": list(categories),
            "series": [{"name": name, "data": [values.get((category, name), 0)
                        for category in categories]} for name in series],
        }

    if component == "Heatmap":
        cells = {}
        for row in rows:
            value = _number(row["value"], "value")
            if row["x"] is None or row["y"] is None or value is None:
                continue
            key = (str(row["x"]), str(row["y"]))
            cells[key] = _number(cells.get(key, 0) + value, "value")
        return {"cells": [{"x": x, "y": y, "value": value} for (x, y), value in cells.items()]}

    if component == "ScatterChart":
        points = []
        for row in rows:
            x, y = _number(row["x"], "x"), _number(row["y"], "y")
            if x is None or y is None:
                continue
            point = {"x": x, "y": y}
            if row.get("label") is not None:
                point["label"] = str(row["label"])
            points.append(point)
        return {"points": points}

    bins = {}
    for row in rows:
        start = _number(row["bin_start"], "bin_start")
        end = _number(row["bin_end"], "bin_end")
        count = _number(row["count"], "count")
        if start is None or end is None or count is None:
            continue
        if start >= end or count < 0 or not count.is_integer():
            raise ValueError("Histogram requires bin_start < bin_end and a nonnegative integer count")
        key = (start, end)
        bins[key] = _number(bins.get(key, 0) + count, "count")
    result = []
    for (start, end), count in sorted(bins.items()):
        if result and start < result[-1]["end"]:
            raise ValueError("Histogram SQL must return non-overlapping bins")
        result.append({"start": start, "end": end, "count": count})
    return {"bins": result}
