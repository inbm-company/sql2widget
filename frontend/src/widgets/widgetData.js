import { resolveWidgetSql } from "../sqlHelpers.js";
import { DISPLAY_KEYS, SQL_COMPONENTS } from "./catalogSettings.js";

export function widgetDefinition(widget, connectionId = null) {
  const sql = resolveWidgetSql(widget);
  if (widget.component === "FilterBar" && !sql) return { ...widget };
  if (!sql && !SQL_COMPONENTS.has(widget.component)) return { ...widget };
  const reference = widget.query_ref || widget.props?.__query_ref;
  const props = {};
  if (DISPLAY_KEYS[widget.component]) {
    for (const key of DISPLAY_KEYS[widget.component]) {
      if (typeof widget.props?.[key] === "string") props[key] = widget.props[key];
    }
  }
  return {
    ...widget,
    sql,
    ...(sql ? { query_ref: { sql, connection_id: reference?.connection_id || connectionId } } : {}),
    props,
  };
}

export function widgetDataUrl(widget, { projectId, conversationId } = {}) {
  if (widget.component === "FilterBar" && !resolveWidgetSql(widget)) return null;
  if (!resolveWidgetSql(widget) && !SQL_COMPONENTS.has(widget.component)) return null;
  if (conversationId && widget.widget_id) {
    return `/api/conversations/${encodeURIComponent(conversationId)}/widgets/${encodeURIComponent(widget.widget_id)}/data`;
  }
  if (projectId && widget.id) {
    return `/api/projects/${encodeURIComponent(projectId)}/stage/widgets/${encodeURIComponent(widget.id)}/data`;
  }
  return null;
}
