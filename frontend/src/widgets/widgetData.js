import { resolveWidgetSql } from "../sqlHelpers.js";

const ANALYTICAL = new Set(["StackedBarChart", "Heatmap", "ScatterChart", "Histogram"]);
const SQL_COMPONENTS = new Set([
  "KpiStat", "DataTable", "RankList", "BarChart", "LineChart", "PieChart", "KpiSparkline",
  "PieTable", "BarTable", ...ANALYTICAL,
]);

export function widgetDefinition(widget, connectionId = null) {
  const sql = resolveWidgetSql(widget);
  if (!sql && !SQL_COMPONENTS.has(widget.component)) return { ...widget };
  const reference = widget.query_ref || widget.props?.__query_ref;
  const props = {};
  if (ANALYTICAL.has(widget.component)) {
    for (const key of ["xLabel", "yLabel"]) {
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
  if (!resolveWidgetSql(widget) && !SQL_COMPONENTS.has(widget.component)) return null;
  if (conversationId && widget.widget_id) {
    return `/api/conversations/${encodeURIComponent(conversationId)}/widgets/${encodeURIComponent(widget.widget_id)}/data`;
  }
  if (projectId && widget.id) {
    return `/api/projects/${encodeURIComponent(projectId)}/stage/widgets/${encodeURIComponent(widget.id)}/data`;
  }
  return null;
}
