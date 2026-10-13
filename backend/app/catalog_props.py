"""SQL contracts for cards, lists, matrices and additional charts."""

import math
from datetime import datetime, timezone

from app.query import jsonable


EXTRA_COMPONENTS = frozenset({
    "CompareCard", "PivotTable", "StatusSummary", "EventTimeline", "KpiGroup",
    "DetailCard", "HorizontalBarChart", "ComboChart", "BoxPlot", "Treemap",
})
SQL_COLUMNS = {
    "CompareCard": ("current", "previous"),
    "PivotTable": ("row", "column", "value"),
    "StatusSummary": ("status", "count"),
    "EventTimeline": ("occurred_at", "title"),
    "KpiGroup": ("label", "value"),
    "DetailCard": (),
    "HorizontalBarChart": ("label", "value"),
    "ComboChart": ("x", "bar_value", "line_value"),
    "BoxPlot": ("label", "minimum", "q1", "median", "q3", "maximum"),
    "Treemap": ("group", "label", "value"),
}
AXIS_COMPONENTS = EXTRA_COMPONENTS | {"LineChart", "StackedBarChart", "Heatmap", "ScatterChart", "Histogram"}
DISPLAY_KEYS = {component: ("xLabel", "yLabel") for component in AXIS_COMPONENTS}
DISPLAY_KEYS["ComboChart"] += ("secondaryYLabel", "barLabel", "lineLabel")
DISPLAY_KEYS["CompareCard"] = ("currentLabel", "previousLabel")


def number(value, column):
    if value is None:
        return None
    try:
        result = float(value)
    except (ValueError, TypeError, OverflowError):
        raise ValueError(f"{column} must be a finite number") from None
    if isinstance(value, bool) or not math.isfinite(result):
        raise ValueError(f"{column} must be a finite number")
    return result


def extra_rows_to_props(component, rows, title):
    for row in rows:
        if any(key not in row for key in SQL_COLUMNS[component]):
            raise ValueError(f"{component} SQL requires columns: {', '.join(SQL_COLUMNS[component])}")

    if component == "CompareCard":
        if len(rows) > 1:
            raise ValueError("CompareCard SQL must return a single comparison row")
        row = rows[0] if rows else {}
        current, previous = number(row.get("current"), "current"), number(row.get("previous"), "previous")
        delta = number(current - previous, "delta") if current is not None and previous is not None else None
        rate = number(delta / abs(previous) * 100, "changeRate") if delta is not None and previous else None
        return {"label": str(row.get("label") or title), "current": current, "previous": previous,
                "delta": delta, "changeRate": rate, "unit": row.get("unit")}

    if component == "PivotTable":
        labels, columns, values = {}, {}, {}
        for row in rows:
            value = number(row["value"], "value")
            if row["row"] is None or row["column"] is None or value is None:
                continue
            label, column = str(row["row"]), str(row["column"])
            labels.setdefault(label, None)
            columns.setdefault(column, f"c{len(columns)}")
            values[label, column] = number(values.get((label, column), 0) + value, "value")
        result = []
        for label in labels:
            entry = {"row": label, **{key: values.get((label, column), 0) for column, key in columns.items()}}
            entry["total"] = number(sum(entry[key] for key in columns.values()), "total")
            result.append(entry)
        totals = {"row": "전체 합계", **{key: number(sum(row[key] for row in result), "total") for key in columns.values()}}
        totals["total"] = number(sum(row["total"] for row in result), "total")
        return {"columns": [{"key": "row", "label": "항목"}]
                + [{"key": key, "label": label} for label, key in columns.items()]
                + [{"key": "total", "label": "합계"}], "rows": result, "totals": totals}

    if component == "StatusSummary":
        counts = {}
        for row in rows:
            value = number(row["count"], "count")
            if row["status"] is None or value is None:
                continue
            if value < 0 or not value.is_integer():
                raise ValueError("StatusSummary count must be a nonnegative integer")
            label = str(row["status"])
            counts[label] = number(counts.get(label, 0) + value, "count")
        total = number(sum(counts.values()), "total")
        return {"total": total, "items": [{"label": label, "value": value,
                "share": value / total * 100 if total else 0} for label, value in counts.items()]}

    if component == "EventTimeline":
        events = []
        for row in rows:
            if row["occurred_at"] is None or row["title"] is None:
                continue
            stamp = str(jsonable(row["occurred_at"]))
            try:
                parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            except ValueError:
                raise ValueError("EventTimeline occurred_at must be an ISO date or timestamp") from None
            events.append((parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed,
                           {"occurredAt": stamp, "title": str(row["title"]),
                            "description": str(row["description"]) if row.get("description") is not None else None}))
        return {"items": [event for _, event in sorted(events, key=lambda entry: entry[0], reverse=True)]}

    if component == "KpiGroup":
        items = []
        for row in rows:
            value = number(row["value"], "value")
            if row["label"] is not None:
                items.append({"label": str(row["label"]), "value": value, "unit": row.get("unit")})
        return {"items": items}

    if component == "DetailCard":
        if len(rows) > 1:
            raise ValueError("DetailCard SQL must return at most one record")
        return {"fields": [{"label": key, "value": jsonable(value)} for key, value in rows[0].items()] if rows else []}

    if component == "HorizontalBarChart":
        data = [(str(row["label"]), number(row["value"], "value")) for row in rows if row["label"] is not None]
        data = [(label, value) for label, value in data if value is not None]
        return {"categories": [label for label, _ in data], "series": [{"name": title, "data": [value for _, value in data]}]}

    if component == "ComboChart":
        return {"points": [{"x": str(row["x"]), "bar": number(row["bar_value"], "bar_value"),
                            "line": number(row["line_value"], "line_value")}
                           for row in rows if row["x"] is not None]}

    if component == "BoxPlot":
        boxes = []
        for row in rows:
            stats = [number(row[key], key) for key in SQL_COLUMNS[component][1:]]
            if row["label"] is None or any(value is None for value in stats):
                continue
            if stats != sorted(stats):
                raise ValueError("BoxPlot requires minimum <= q1 <= median <= q3 <= maximum")
            outliers = row.get("outliers") or []
            if not isinstance(outliers, (list, tuple)):
                raise ValueError("BoxPlot outliers must be an array of numbers")
            outliers = [number(value, "outliers") for value in outliers if value is not None]
            if any(stats[0] <= value <= stats[-1] for value in outliers):
                raise ValueError("BoxPlot outliers must lie outside the whiskers")
            boxes.append({"label": str(row["label"]), **dict(zip(SQL_COLUMNS[component][1:], stats)), "outliers": outliers})
        return {"boxes": boxes}

    groups, values = {}, {}
    for row in rows:
        value = number(row["value"], "value")
        if row["group"] is None or row["label"] is None or value is None:
            continue
        if value < 0:
            raise ValueError("Treemap values must be nonnegative")
        group, label = str(row["group"]), str(row["label"])
        groups.setdefault(group, f"g{len(groups)}")
        values[group, label] = number(values.get((group, label), 0) + value, "value")
    active = {group for (group, _), value in values.items() if value > 0}
    nodes = ([{"id": "root", "parentId": None, "label": "전체", "group": "", "value": 0}] if active else [])
    nodes += [{"id": key, "parentId": "root", "label": group, "group": group, "value": 0}
             for group, key in groups.items() if group in active]
    nodes += [{"id": f"n{i}", "parentId": groups[group], "label": label, "group": group, "value": value}
              for i, ((group, label), value) in enumerate(values.items()) if value > 0]
    return {"nodes": nodes}
