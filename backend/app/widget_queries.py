"""Persist query definitions, and fetch widget data under current permissions."""

from app.config import ALLOWED_COMPONENTS
from app.query import QueryError, execute_readonly
from app.repositories import connections
from app.widget_props import ANALYTICAL_COMPONENTS, rows_to_props
from app.catalog_props import DISPLAY_KEYS


SQL_COMPONENTS = ALLOWED_COMPONENTS - {"MarkdownBlock", "SourceList"}


def display_props(component, props):
    """SQL widgets store only supported display settings, never result values."""
    return {key: props[key] for key in DISPLAY_KEYS.get(component, ()) if isinstance(props.get(key), str)}


def widget_definition(widget, connection_id=None):
    """Normalize both new definitions and legacy SQL/result snapshots in memory."""
    props = dict(widget.get("props") or {})
    stored_reference = props.pop("__query_ref", None)
    reference = widget.get("query_ref") or stored_reference or {}
    legacy_sql = props.pop("__sql", None)
    sql = (reference.get("sql") or widget.get("sql") or legacy_sql or "").strip()
    result = {**widget, "props": props}
    if widget.get("component") in SQL_COMPONENTS and not (widget.get("component") == "FilterBar" and not sql):
        result["props"] = display_props(widget["component"], props)
    if sql:
        result.update(sql=sql, query_ref={
            "sql": sql, "connection_id": reference.get("connection_id") or connection_id,
        }, props=display_props(widget.get("component"), props))
    return result


def stored_widget_props(widget):
    definition = widget_definition(widget)
    props = dict(definition["props"])
    if definition.get("query_ref"):
        props["__query_ref"] = definition["query_ref"]
    return props


class WidgetDataError(Exception):
    def __init__(self, status_code, detail):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def load_widget_data(widget, user):
    definition = widget_definition(widget)
    reference = definition.get("query_ref") or {}
    connection_id = reference.get("connection_id")
    if not reference.get("sql") or not connection_id:
        raise WidgetDataError(409, "조회 SQL 또는 원본 DB 정보가 없습니다. 질문을 다시 실행해 위젯을 추가해 주세요.")
    component = definition.get("component")
    if component not in SQL_COMPONENTS:
        raise WidgetDataError(400, "데이터 조회를 지원하지 않는 위젯입니다.")
    connection = connections.get_connection(connection_id, user["tenant_id"])
    if not connection:
        raise WidgetDataError(404, "원본 DB 연결을 찾을 수 없습니다.")
    allowed = connections.allowed_tables_for_role(user["tenant_id"], connection_id, user["role"])
    if not allowed:
        raise WidgetDataError(403, "이 DB에서 조회할 수 있는 테이블 권한이 없습니다.")
    try:
        rows = execute_readonly(connections.connection_url(connection), reference["sql"], allowed_tables=allowed)
        props = {**definition["props"], **rows_to_props(component, rows, definition.get("title") or component)}
    except QueryError as exc:
        raise WidgetDataError(400, str(exc)) from exc
    except ValueError as exc:
        raise WidgetDataError(400, "조회 결과가 위젯의 데이터 형식과 맞지 않습니다.") from exc
    except Exception as exc:
        # Connection/driver errors may contain credentials; never send raw errors.
        raise WidgetDataError(502, "위젯 데이터를 조회하지 못했습니다. DB 연결과 SQL을 확인해 주세요.") from exc
    return {"props": props, "count": len(rows)}
