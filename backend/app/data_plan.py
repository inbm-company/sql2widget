"""Generate independent datasets, then choose multiple compatible result views."""

from app.agent_plan import model_context
from app.llm import json_with_llm
from app.prompts import SQL_GENERATION_HINT, WIDGET_SELECTION_HINT
from app.widget_queries import SQL_COMPONENTS, display_props
from app.catalog_props import DISPLAY_KEYS
from app.widget_bindings import COLUMN_ROLES, NUMERIC_ROLES, REQUIRED_ROLES, SCALAR_COMPONENTS, validate_binding

MAX_WIDGETS = 20
MAX_QUERIES = 20


class DataPlanError(RuntimeError):
    pass


def _ask(hint, content, context, deadline):
    result = json_with_llm(hint, content, **model_context(context, deadline))
    if not isinstance(result.get("result"), dict):
        raise DataPlanError("데이터 계획 모델이 유효한 JSON을 반환하지 못했습니다.")
    return result["result"], {key: result.get(key) for key in ("provider", "model")}


def select_widgets(message, *, result, history, context, deadline, existing_widgets=None, feedback=None, original_request=None):
    data, model = _ask(WIDGET_SELECTION_HINT, {"question": message, "user_request": original_request or message, "result": result,
        "history": history, "existing_widgets": existing_widgets or [], "feedback": feedback,
        "allowed_components": sorted(SQL_COMPONENTS), "max_widgets": MAX_WIDGETS,
        "column_roles": COLUMN_ROLES, "required_roles": {key: sorted(value) for key, value in REQUIRED_ROLES.items()},
        "display_keys": DISPLAY_KEYS}, context, deadline)
    raw = data.get("widgets")
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_WIDGETS:
        raise DataPlanError("위젯 선택 결과가 비어 있거나 개수 한도를 초과했습니다.")
    widgets = []
    columns = {column["name"]: column["type"] for column in result["columns"]}
    for item in raw:
        if not isinstance(item, dict):
            raise DataPlanError("위젯 선택 결과 형식이 올바르지 않습니다.")
        component = item.get("component")
        if not isinstance(component, str) or component not in SQL_COMPONENTS:
            component = "DataTable"
        mapping = item.get("column_map", {})
        if component == "DataTable":
            mapping = {}
        try:
            mapping = validate_binding(component, mapping, columns)
        except ValueError as exc:
            raise DataPlanError(str(exc)) from exc
        if any(columns[mapping[role]] != "numeric" for role in NUMERIC_ROLES.get(component, set())):
            raise DataPlanError(f"{component}의 수치 역할은 실제 수치 컬럼에 연결해야 합니다.")
        if component in SCALAR_COMPONENTS and result["row_count"] > 1:
            raise DataPlanError(f"{component}에 여러 행을 단일 값으로 임의 축약할 수 없습니다.")
        props = item.get("props") if isinstance(item.get("props"), dict) else {}
        widgets.append({"component": component, "title": str(item.get("title") or result["title"]),
                        "props": display_props(component, {**props, "column_map": mapping})})
    return widgets, model


def generate_sql(message, *, schema, history, references, context, deadline, repair_hint=None, original_request=None):
    data, model = _ask(SQL_GENERATION_HINT, {"question": message, "user_request": original_request or message, "schema": schema,
        "history": history, "matched_questions": references, "max_queries": MAX_QUERIES,
        "repair_hint": repair_hint}, context, deadline)
    queries = data.get("queries")
    if not isinstance(queries, list) or not 1 <= len(queries) <= MAX_QUERIES:
        raise DataPlanError("SQL 생성 결과가 비어 있거나 조회 개수 한도를 초과했습니다.")
    datasets = []
    for query in queries:
        if not isinstance(query, dict):
            raise DataPlanError("SQL 생성 결과 형식이 올바르지 않습니다.")
        sql = query.get("sql")
        if not isinstance(sql, str) or not sql.strip():
            raise DataPlanError("조회 SQL이 비어 있습니다.")
        datasets.append({"sql": sql.strip(), "title": str(query.get("title") or "조회 결과"),
                         "purpose": str(query.get("purpose") or message)})
    return {"summary": str(data.get("summary") or "요청한 조회 결과를 준비했습니다."), "queries": datasets}, model
