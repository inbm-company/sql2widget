"""Convert SQL results into runtime props for the fixed widget catalog."""

import math
from typing import Any
from app.catalog_props import EXTRA_COMPONENTS, extra_rows_to_props


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


def rows_to_props(component: str, rows: list[dict[str, Any]], title: str) -> dict[str, Any]:
    if component in EXTRA_COMPONENTS:
        return extra_rows_to_props(component, rows, title)
    if component in ANALYTICAL_COMPONENTS:
        return analytical_rows_to_props(component, rows)
    if not rows:
        if component == "KpiStat":
            return {"label": title, "value": 0}
        if component == "DataTable":
            return {"columns": [{"key": "info", "label": "Info"}], "rows": [{"info": "결과 없음"}]}
        if component == "FilterBar":
            return {"columns": [], "rows": []}
        if component == "BarChart":
            return {"categories": [], "series": [{"name": "value", "data": []}]}
        if component == "LineChart":
            return {"series": [{"name": title, "points": []}]}
        if component == "RankList":
            return {"items": []}
        if component == "PieChart":
            return {"slices": []}
        return {}

    keys = list(rows[0].keys())
    if component == "KpiStat":
        value_key = "value" if "value" in keys else keys[-1]
        return {"label": title, "value": rows[0][value_key], "unit": rows[0].get("unit")}
    if component == "DataTable":
        return {
            "columns": [{"key": k, "label": k} for k in keys],
            "rows": [{k: r.get(k) for k in keys} for r in rows],
        }
    if component == "FilterBar":
        return {"columns": [{"key": key, "label": key} for key in keys], "rows": rows}
    if component == "RankList":
        label_key = "hostname" if "hostname" in keys else keys[0]
        value_key = "attack_count" if "attack_count" in keys else keys[-1]
        meta_key = "top_method" if "top_method" in keys else None
        items = []
        for i, r in enumerate(rows, start=1):
            items.append(
                {
                    "rank": i,
                    "label": str(r.get(label_key)),
                    "value": r.get(value_key),
                    "meta": str(r.get(meta_key)) if meta_key else None,
                }
            )
        return {"items": items}
    if component == "BarChart":
        cat_key = "hostname" if "hostname" in keys else keys[0]
        val_key = "attack_count" if "attack_count" in keys else keys[-1]
        return {
            "categories": [str(r.get(cat_key)) for r in rows],
            "series": [{"name": val_key, "data": [r.get(val_key) or 0 for r in rows]}],
        }
    if component == "LineChart":
        if "series" in keys:
            if "x" not in keys or "y" not in keys:
                raise ValueError("Multi-series LineChart SQL requires x, y, series columns")
            from app.catalog_props import number
            names, positions, points = {}, {}, {}
            for row in rows:
                if row["series"] is None or row["x"] is None:
                    continue
                name, x = str(row["series"]), str(row["x"])
                if (name, x) in points:
                    raise ValueError("LineChart SQL must return unique x/series pairs")
                names.setdefault(name, None)
                positions.setdefault(x, None)
                points[name, x] = number(row["y"], "y")
            return {"series": [{"name": name, "points": [{"x": x, "y": points.get((name, x))}
                               for x in positions]} for name in names]}
        x_key = "x" if "x" in keys else keys[0]
        y_key = "y" if "y" in keys else keys[-1]
        return {
            "series": [
                {
                    "name": title,
                    "points": [{"x": str(r.get(x_key)), "y": r.get(y_key)} for r in rows],
                }
            ]
        }
    if component == "PieChart":
        label_key = keys[0]
        value_key = keys[-1]
        return {
            "slices": [
                {"label": str(r.get(label_key)), "value": r.get(value_key) or 0} for r in rows
            ]
        }
    if component == "PieTable":
        label_key = "label" if "label" in keys else keys[0]
        value_key = "value" if "value" in keys else keys[-1]
        slices = [
            {"label": str(r.get(label_key)), "value": r.get(value_key) or 0} for r in rows
        ]
        return {
            "slices": slices,
            "columns": [
                {"key": "label", "label": label_key},
                {"key": "value", "label": value_key},
            ],
            "rows": slices,
        }
    if component == "BarTable":
        cat_key = "hostname" if "hostname" in keys else ("label" if "label" in keys else keys[0])
        val_key = "attack_count" if "attack_count" in keys else ("value" if "value" in keys else keys[-1])
        meta_key = "top_method" if "top_method" in keys else None
        categories = [str(r.get(cat_key)) for r in rows]
        data = [r.get(val_key) or 0 for r in rows]
        table_rows = [
            {
                "label": str(r.get(cat_key)),
                "value": r.get(val_key),
                **({"meta": r.get(meta_key)} if meta_key else {}),
            }
            for r in rows
        ]
        cols = [
            {"key": "label", "label": cat_key},
            {"key": "value", "label": val_key},
        ]
        if meta_key:
            cols.append({"key": "meta", "label": meta_key})
        return {
            "label": title,
            "value": sum(data) if data else 0,
            "categories": categories,
            "series": [{"name": val_key, "data": data}],
            "columns": cols,
            "rows": table_rows,
        }
    if component == "KpiSparkline":
        value_key = "value" if "value" in keys else keys[-1]
        points = []
        if "x" in keys and "y" in keys:
            points = [{"x": str(r.get("x")), "y": r.get("y")} for r in rows]
        return {
            "label": title,
            "value": rows[0].get(value_key),
            "points": points
            or [{"x": str(i), "y": r.get(value_key) or 0} for i, r in enumerate(rows)],
        }
    return {"columns": [{"key": k, "label": k} for k in keys], "rows": rows}
