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

const FALLBACK_BY_TITLE = {
  "지난달 서버별 공격": `SELECT s.hostname,
       COUNT(*)::int AS attack_count,
       MODE() WITHIN GROUP (ORDER BY a.attack_method) AS top_method
FROM attack_events a
JOIN servers s ON s.id = a.server_id
WHERE a.occurred_at >= date_trunc('month', now()) - interval '1 month'
  AND a.occurred_at < date_trunc('month', now())
GROUP BY s.hostname
ORDER BY attack_count DESC`,
  "공격 유형 비중": `SELECT attack_method AS label, COUNT(*)::int AS value
FROM attack_events
WHERE occurred_at >= now() - interval '90 days'
GROUP BY attack_method
ORDER BY value DESC`,
  "심각도별 집계": `SELECT severity, COUNT(*)::int AS value
FROM attack_events
WHERE occurred_at >= now() - interval '30 days'
GROUP BY severity
ORDER BY value DESC`,
  Critical: `SELECT COUNT(*)::int AS value, 'critical' AS unit
FROM attack_events
WHERE severity = 'critical' AND occurred_at >= now() - interval '30 days'`,
  High: `SELECT COUNT(*)::int AS value, 'high' AS unit
FROM attack_events
WHERE severity = 'high' AND occurred_at >= now() - interval '30 days'`,
  "Medium/Low": `SELECT COUNT(*)::int AS value, 'medium' AS unit
FROM attack_events
WHERE severity IN ('medium', 'low') AND occurred_at >= now() - interval '30 days'`,
  "자산별 공격 건수": `SELECT s.hostname,
       COUNT(a.id)::int AS attack_count,
       MAX(a.occurred_at)::date AS last_seen,
       s.zone,
       s.criticality
FROM servers s
LEFT JOIN attack_events a ON a.server_id = s.id
  AND a.occurred_at >= now() - interval '90 days'
GROUP BY s.id, s.hostname, s.zone, s.criticality
ORDER BY attack_count DESC, s.criticality DESC
LIMIT 10`,
  "자산 위험도 상세": `SELECT s.hostname,
       COUNT(a.id)::int AS attack_count,
       MAX(a.occurred_at)::date AS last_seen,
       s.zone,
       s.criticality
FROM servers s
LEFT JOIN attack_events a ON a.server_id = s.id
  AND a.occurred_at >= now() - interval '90 days'
GROUP BY s.id, s.hostname, s.zone, s.criticality
ORDER BY attack_count DESC, s.criticality DESC
LIMIT 10`,
  "최근 7일 공격 추이": `SELECT to_char(date_trunc('day', occurred_at), 'MM-DD') AS x,
       COUNT(*)::int AS y
FROM attack_events
WHERE occurred_at >= now() - interval '7 days'
GROUP BY date_trunc('day', occurred_at)
ORDER BY date_trunc('day', occurred_at)`,
  "열린 취약점": `SELECT v.cve, s.hostname, v.score, v.status
FROM vulnerability_findings v
JOIN servers s ON s.id = v.asset_id
WHERE v.status = 'open'
ORDER BY v.score DESC`,
  "차단 IP": `SELECT host(ip) AS ip, reason, hit_count, blocked_at::date AS blocked_date
FROM blocked_ips
ORDER BY hit_count DESC
LIMIT 15`,
  인시던트: `SELECT i.title, i.status, i.severity, s.hostname, i.opened_at::date AS opened
FROM incidents i
LEFT JOIN servers s ON s.id = i.asset_id
ORDER BY i.opened_at DESC`,
  "진행 중 인시던트": `SELECT i.title, i.status, i.severity, s.hostname, i.opened_at::date AS opened
FROM incidents i
LEFT JOIN servers s ON s.id = i.asset_id
ORDER BY i.opened_at DESC`,
};

const FALLBACK_BY_COMPONENT = {
  BarChart: "-- SQL unavailable for this widget\nSELECT 1",
  LineChart: "-- SQL unavailable for this widget\nSELECT 1",
  DataTable: "-- SQL unavailable for this widget\nSELECT 1",
  RankList: "-- SQL unavailable for this widget\nSELECT 1",
  KpiStat: "-- SQL unavailable for this widget\nSELECT 1",
  PieChart: "-- SQL unavailable for this widget\nSELECT 1",
};

export function canShowSql(widget) {
  if (!widget) return false;
  if (widget.sql || widget.query_ref?.sql || widget.props?.__sql) return true;
  return SQL_COMPONENTS.has(widget.component);
}

export function resolveWidgetSql(widget) {
  if (!widget) return "";
  const direct = widget.sql || widget.query_ref?.sql || widget.props?.__sql;
  if (direct) return String(direct).trim();
  if (widget.title && FALLBACK_BY_TITLE[widget.title]) {
    return FALLBACK_BY_TITLE[widget.title];
  }
  return FALLBACK_BY_COMPONENT[widget.component] || "";
}
