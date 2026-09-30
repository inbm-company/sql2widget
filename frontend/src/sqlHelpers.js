const SQL_COMPONENTS = new Set([
  "KpiStat",
  "DataTable",
  "RankList",
  "BarChart",
  "LineChart",
  "PieChart",
  "FilterBar",
  "KpiSparkline",
  "PieTable",
  "BarTable",
]);

export function canShowSql(widget) {
  if (!widget) return false;
  if (widget.sql || widget.query_ref?.sql || widget.props?.__sql) return true;
  return SQL_COMPONENTS.has(widget.component);
}

// Only ever shows the SQL the backend actually attached to this widget — never
// a guessed/hardcoded stand-in. If none was attached, the caller hides the toggle.
export function resolveWidgetSql(widget) {
  if (!widget) return "";
  const direct = widget.sql || widget.query_ref?.sql || widget.props?.__sql;
  return direct ? String(direct).trim() : "";
}
