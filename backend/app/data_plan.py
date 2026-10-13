"""Select fixed widgets first; generate only their SQL in a separate model call."""

from app.agent_plan import model_context
from app.llm import json_with_llm
from app.prompts import SQL_GENERATION_HINT, WIDGET_SELECTION_HINT
from app.widget_queries import SQL_COMPONENTS, display_props

MAX_WIDGETS = 20


class DataPlanError(RuntimeError):
    pass


def _ask(hint, content, context, deadline):
    result = json_with_llm(hint, content, **model_context(context, deadline))
    if not isinstance(result.get("result"), dict):
        raise DataPlanError(f"{result.get('provider') or 'LLM'} request failed: "
                            f"{result.get('error') or 'invalid data planning response'}")
    return result["result"], {key: result.get(key) for key in ("provider", "model")}


def select_widgets(message, *, schema, history, references, context, deadline):
    data, model = _ask(WIDGET_SELECTION_HINT, {"question": message, "schema": schema,
        "history": history, "matched_questions": references,
        "allowed_components": sorted(SQL_COMPONENTS), "max_widgets": MAX_WIDGETS}, context, deadline)
    raw = data.get("widgets")
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_WIDGETS:
        raise DataPlanError("위젯 선택 결과가 비어 있거나 개수 한도를 초과했습니다.")
    widgets = []
    for item in raw:
        if not isinstance(item, dict):
            raise DataPlanError("위젯 선택 결과 형식이 올바르지 않습니다.")
        component = item.get("component")
        if not isinstance(component, str) or component not in SQL_COMPONENTS:
            component = "DataTable"
        if not isinstance(item.get("purpose"), str) or not item["purpose"].strip():
            raise DataPlanError("선택된 위젯의 데이터 목적이 없습니다.")
        widgets.append({"component": component, "title": str(item.get("title") or component),
            "purpose": item["purpose"], "props": display_props(component,
                item.get("props") if isinstance(item.get("props"), dict) else {})})
    return {"summary": str(data.get("summary") or "요청한 데이터 위젯을 준비했습니다."),
        "artifact_type": "dashboard" if len(widgets) > 1 else "widget", "widgets": widgets}, model


def generate_sql(message, selection, *, schema, history, references, context, deadline, repair_hint=None):
    data, model = _ask(SQL_GENERATION_HINT, {"question": message, "schema": schema,
        "history": history, "matched_questions": references, "widgets": selection["widgets"],
        "repair_hint": repair_hint}, context, deadline)
    queries = data.get("queries")
    if not isinstance(queries, list) or len(queries) != len(selection["widgets"]):
        raise DataPlanError("선택한 위젯마다 SQL이 하나씩 필요합니다.")
    by_index = {}
    for query in queries:
        if not isinstance(query, dict):
            raise DataPlanError("SQL 생성 결과 형식이 올바르지 않습니다.")
        index, sql = query.get("widget_index"), query.get("sql")
        if type(index) is not int or not 0 <= index < len(queries) or index in by_index:
            raise DataPlanError("SQL과 위젯의 연결 인덱스가 올바르지 않습니다.")
        if not isinstance(sql, str) or not sql.strip():
            raise DataPlanError("위젯의 조회 SQL이 비어 있습니다.")
        by_index[index] = sql.strip()
    widgets = [{key: value for key, value in widget.items() if key != "purpose"}
               | {"sql": by_index[index]} for index, widget in enumerate(selection["widgets"])]
    return {**selection, "widgets": widgets}, model
