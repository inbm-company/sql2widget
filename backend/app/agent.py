"""Mock agent: SOC scenarios backed by customer DB SELECT results."""

from __future__ import annotations

import secrets
from typing import Any

from app.config import ALLOWED_COMPONENTS, DEMO_CUSTOMER_DATABASE_URL
from app.query import QueryError, execute_readonly


SOC_TABLES = {
    "servers",
    "attack_events",
    "incidents",
    "vulnerability_findings",
    "blocked_ips",
}

GLOBAL_TABLES = {
    "regions",
    "products",
    "monthly_sales",
}

_active_db_url = DEMO_CUSTOMER_DATABASE_URL
_active_tables: set[str] = SOC_TABLES

SAMPLE_QUESTIONS = [
    "지난달 공격당한 서버들의 공격 순위, 방법, 해결 방안을 보여줘.",
    "공격 유형별 비중을 보여줘.",
    "심각도별 공격 현황을 보여줘.",
    "자산별 위험도 순위를 보여줘.",
    "최근 7일 공격 추이를 보여줘.",
    "열린 취약점 목록을 보여줘.",
    "차단된 IP 목록을 보여줘.",
    "SOC 보안 현황을 보고서 형태로 만들어줘.",
]


def _wid(prefix: str = "wgt") -> str:
    return f"{prefix}_{secrets.token_hex(6)}"


def _aid() -> str:
    return f"art_{secrets.token_hex(6)}"


def sanitize_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    widgets = []
    for w in artifact.get("widgets") or []:
        component = w.get("component")
        if component not in ALLOWED_COMPONENTS:
            component = "DataTable"
            if "columns" not in (w.get("props") or {}):
                w = {
                    **w,
                    "props": {
                        "columns": [{"key": "info", "label": "Info"}],
                        "rows": [{"info": "Unsupported component fell back to table"}],
                    },
                }
        widgets.append({**w, "component": component, "widget_id": w.get("widget_id") or _wid()})
    return {**artifact, "artifact_id": artifact.get("artifact_id") or _aid(), "widgets": widgets}


def _query(sql: str) -> list[dict[str, Any]]:
    return execute_readonly(
        _active_db_url,
        sql,
        allowed_tables=_active_tables,
    )


def _db_widget(component: str, title: str, sql: str) -> dict[str, Any]:
    from app.agent_service import rows_to_props

    rows = _query(sql)
    return {
        "widget_id": _wid(),
        "component": component,
        "title": title,
        "sql": sql.strip(),
        "props": rows_to_props(component, rows, title),
    }


SQL_ATTACK_RANK = """
SELECT s.hostname,
       COUNT(*)::int AS attack_count,
       MODE() WITHIN GROUP (ORDER BY a.attack_method) AS top_method
FROM attack_events a
JOIN servers s ON s.id = a.server_id
WHERE a.occurred_at >= date_trunc('month', now()) - interval '1 month'
  AND a.occurred_at < date_trunc('month', now())
GROUP BY s.hostname
ORDER BY attack_count DESC
""".strip()

SQL_ATTACK_METHOD_PIE = """
SELECT attack_method AS label, COUNT(*)::int AS value
FROM attack_events
WHERE occurred_at >= now() - interval '90 days'
GROUP BY attack_method
ORDER BY value DESC
""".strip()

SQL_SEVERITY_TABLE = """
SELECT severity, COUNT(*)::int AS value
FROM attack_events
WHERE occurred_at >= now() - interval '30 days'
GROUP BY severity
ORDER BY value DESC
""".strip()

SQL_SEVERITY_CRITICAL = """
SELECT COUNT(*)::int AS value, 'critical' AS unit
FROM attack_events
WHERE severity = 'critical' AND occurred_at >= now() - interval '30 days'
""".strip()

SQL_SEVERITY_HIGH = """
SELECT COUNT(*)::int AS value, 'high' AS unit
FROM attack_events
WHERE severity = 'high' AND occurred_at >= now() - interval '30 days'
""".strip()

SQL_SEVERITY_MEDIUM = """
SELECT COUNT(*)::int AS value, 'medium' AS unit
FROM attack_events
WHERE severity IN ('medium', 'low') AND occurred_at >= now() - interval '30 days'
""".strip()

SQL_ASSET_RISK = """
SELECT s.hostname,
       COUNT(a.id)::int AS attack_count,
       MAX(a.occurred_at)::date AS last_seen,
       s.zone,
       s.criticality
FROM servers s
LEFT JOIN attack_events a ON a.server_id = s.id
  AND a.occurred_at >= now() - interval '90 days'
GROUP BY s.id, s.hostname, s.zone, s.criticality
ORDER BY attack_count DESC, s.criticality DESC
LIMIT 10
""".strip()

SQL_TREND_7D = """
SELECT to_char(date_trunc('day', occurred_at), 'MM-DD') AS x,
       COUNT(*)::int AS y
FROM attack_events
WHERE occurred_at >= now() - interval '7 days'
GROUP BY date_trunc('day', occurred_at)
ORDER BY date_trunc('day', occurred_at)
""".strip()

SQL_VULNS = """
SELECT v.cve, s.hostname, v.score, v.status
FROM vulnerability_findings v
JOIN servers s ON s.id = v.asset_id
WHERE v.status = 'open'
ORDER BY v.score DESC
""".strip()

SQL_BLOCKED = """
SELECT host(ip) AS ip, reason, hit_count, blocked_at::date AS blocked_date
FROM blocked_ips
ORDER BY hit_count DESC
LIMIT 15
""".strip()

SQL_INCIDENTS = """
SELECT i.title, i.status, i.severity, s.hostname, i.opened_at::date AS opened
FROM incidents i
LEFT JOIN servers s ON s.id = i.asset_id
ORDER BY i.opened_at DESC
""".strip()


def _attack_artifact() -> dict[str, Any]:
    widgets = [
        _db_widget("BarTable", "지난달 서버별 공격", SQL_ATTACK_RANK),
        {
            "widget_id": _wid(),
            "component": "MarkdownBlock",
            "title": "해결 방안",
            "props": {
                "markdown": (
                    "### 권장 조치\n"
                    "- SSH 무차별 대입: fail2ban·키 기반 인증 강화\n"
                    "- 랜섬웨어: 백업 검증 및 네트워크 세그먼트 분리\n"
                    "- DDoS: 엣지 레이트리밋 및 트래픽 scrubbing\n"
                ),
                "citations": [
                    {"title": "SSH Hardening Guide", "section": "3.2", "ref": "doc://ssh-hardening"}
                ],
            },
        },
        {
            "widget_id": _wid(),
            "component": "SourceList",
            "title": "문서 출처",
            "props": {
                "sources": [
                    {
                        "title": "SSH Hardening Guide",
                        "version": "1.4",
                        "section": "3.2 Brute force",
                    },
                    {
                        "title": "Incident Playbook",
                        "version": "2.0",
                        "section": "Ransomware",
                    },
                ]
            },
        },
    ]
    return {"artifact_id": _aid(), "type": "dashboard", "widgets": widgets}


def _method_pie_artifact() -> dict[str, Any]:
    return {
        "artifact_id": _aid(),
        "type": "dashboard",
        "widgets": [
            _db_widget("PieTable", "공격 유형 비중", SQL_ATTACK_METHOD_PIE),
        ],
    }


def _severity_artifact() -> dict[str, Any]:
    return {
        "artifact_id": _aid(),
        "type": "dashboard",
        "widgets": [
            _db_widget("KpiStat", "Critical", SQL_SEVERITY_CRITICAL),
            _db_widget("KpiStat", "High", SQL_SEVERITY_HIGH),
            _db_widget("KpiStat", "Medium/Low", SQL_SEVERITY_MEDIUM),
            _db_widget("DataTable", "심각도별 집계", SQL_SEVERITY_TABLE),
        ],
    }


def _asset_risk_artifact() -> dict[str, Any]:
    rank = _db_widget("RankList", "자산별 공격 건수", SQL_ASSET_RISK)
    table = _db_widget("DataTable", "자산 위험도 상세", SQL_ASSET_RISK)
    return {
        "artifact_id": _aid(),
        "type": "dashboard",
        "widgets": [rank, table],
    }


def _trend_artifact() -> dict[str, Any]:
    return {
        "artifact_id": _aid(),
        "type": "dashboard",
        "widgets": [
            _db_widget("LineChart", "최근 7일 공격 추이", SQL_TREND_7D),
        ],
    }


def _vuln_artifact() -> dict[str, Any]:
    return {
        "artifact_id": _aid(),
        "type": "dashboard",
        "widgets": [
            _db_widget("DataTable", "열린 취약점", SQL_VULNS),
        ],
    }


def _blocked_artifact() -> dict[str, Any]:
    return {
        "artifact_id": _aid(),
        "type": "dashboard",
        "widgets": [
            _db_widget("DataTable", "차단 IP", SQL_BLOCKED),
        ],
    }


def _report_artifact() -> dict[str, Any]:
    critical = _query(SQL_SEVERITY_CRITICAL)
    high = _query(SQL_SEVERITY_HIGH)
    open_vulns = _query(SQL_VULNS)
    crit_n = critical[0]["value"] if critical else 0
    high_n = high[0]["value"] if high else 0
    vuln_n = len(open_vulns)
    widgets = [
        {
            "widget_id": _wid(),
            "component": "MarkdownBlock",
            "title": "SOC 보고서 요약",
            "props": {
                "markdown": (
                    "## SOC 보안 현황 보고서\n"
                    f"- 최근 30일 **critical** 공격 {crit_n}건, **high** {high_n}건\n"
                    f"- 미해결 취약점 **{vuln_n}**건\n"
                    "- DMZ·본사·클라우드 구역 자산을 통합 모니터링 중\n"
                    "- 우선 조치: critical/high 인시던트 및 상위 CVSS 취약점 패치\n"
                ),
                "citations": [],
            },
        },
        _db_widget("KpiStat", "Critical (30d)", SQL_SEVERITY_CRITICAL),
        _db_widget("KpiStat", "High (30d)", SQL_SEVERITY_HIGH),
        _db_widget("BarTable", "지난달 서버별 공격", SQL_ATTACK_RANK),
        _db_widget("DataTable", "진행 중 인시던트", SQL_INCIDENTS),
        _db_widget("DataTable", "열린 취약점", SQL_VULNS),
    ]
    return {"artifact_id": _aid(), "type": "report", "widgets": widgets}


def _help_artifact() -> dict[str, Any]:
    bullets = "\n".join(f"- {q}" for q in SAMPLE_QUESTIONS)
    return {
        "artifact_id": _aid(),
        "type": "widget",
        "widgets": [
            {
                "widget_id": _wid(),
                "component": "MarkdownBlock",
                "title": "안내",
                "props": {
                    "markdown": f"샘플 질문을 시도해 보세요.\n{bullets}\n",
                    "citations": [],
                },
            }
        ],
    }


GLOBAL_SAMPLE_QUESTIONS = [
    "지역별 매출 순위를 보여줘.",
    "제품별 매출 비중을 보여줘.",
    "최근 12개월 매출 추이를 보여줘.",
    "글로벌 매출 현황을 보고서 형태로 만들어줘.",
]

SQL_REGION_SALES = """
SELECT r.name AS region, SUM(ms.revenue)::numeric AS revenue
FROM monthly_sales ms
JOIN regions r ON r.id = ms.region_id
WHERE ms.month >= date_trunc('month', CURRENT_DATE - interval '11 months')
GROUP BY r.name
ORDER BY revenue DESC
"""

SQL_PRODUCT_PIE = """
SELECT p.name AS product, SUM(ms.revenue)::numeric AS revenue
FROM monthly_sales ms
JOIN products p ON p.id = ms.product_id
WHERE ms.month >= date_trunc('month', CURRENT_DATE - interval '11 months')
GROUP BY p.name
ORDER BY revenue DESC
"""

SQL_SALES_TREND = """
SELECT to_char(ms.month, 'YYYY-MM') AS month, SUM(ms.revenue)::numeric AS revenue
FROM monthly_sales ms
WHERE ms.month >= date_trunc('month', CURRENT_DATE - interval '11 months')
GROUP BY ms.month
ORDER BY ms.month
"""

SQL_GLOBAL_TOTAL = """
SELECT SUM(revenue)::numeric AS value
FROM monthly_sales
WHERE month >= date_trunc('month', CURRENT_DATE - interval '11 months')
"""


def _global_help_artifact() -> dict[str, Any]:
    bullets = "\n".join(f"- {q}" for q in GLOBAL_SAMPLE_QUESTIONS)
    return {
        "artifact_id": _aid(),
        "type": "widget",
        "widgets": [
            {
                "widget_id": _wid(),
                "component": "MarkdownBlock",
                "title": "안내",
                "props": {
                    "markdown": f"글로벌 sales 데모 질문:\n{bullets}\n",
                    "citations": [],
                },
            }
        ],
    }


def _global_report_artifact() -> dict[str, Any]:
    totals = _query(SQL_GLOBAL_TOTAL)
    total_rev = totals[0]["value"] if totals else 0
    widgets = [
        {
            "widget_id": _wid(),
            "component": "MarkdownBlock",
            "title": "Global Sales Report",
            "props": {
                "markdown": (
                    "## Global Sales Overview\n"
                    f"- 최근 12개월 총 매출 **{total_rev}**\n"
                    "- 6개 지역 · 4개 제품 라인업\n"
                    "- APAC·EMEA·North America가 상위 매출 권역\n"
                ),
                "citations": [],
            },
        },
        _db_widget("KpiStat", "Total Revenue (12m)", SQL_GLOBAL_TOTAL),
        _db_widget("BarTable", "Region sales", SQL_REGION_SALES),
        _db_widget("PieTable", "Product mix", SQL_PRODUCT_PIE),
        _db_widget("LineChart", "Monthly trend", SQL_SALES_TREND),
    ]
    return {"artifact_id": _aid(), "type": "report", "widgets": widgets}


def _run_global_mock(message: str) -> tuple[str, dict[str, Any]]:
    text = message.strip()
    lower = text.lower()

    try:
        if "보고서" in text or "report" in lower or "global" in lower or "글로벌" in text:
            artifact = sanitize_artifact(_global_report_artifact())
            return "글로벌 매출 현황을 보고서 형태로 정리했습니다.", artifact

        if any(k in text for k in ("제품", "비중", "pie", "product")):
            artifact = sanitize_artifact(
                {
                    "artifact_id": _aid(),
                    "type": "dashboard",
                    "widgets": [_db_widget("PieTable", "Product revenue mix", SQL_PRODUCT_PIE)],
                }
            )
            return "제품별 매출 비중입니다.", artifact

        if any(k in text for k in ("추이", "월별", "trend", "12개월", "12월")):
            artifact = sanitize_artifact(
                {
                    "artifact_id": _aid(),
                    "type": "dashboard",
                    "widgets": [_db_widget("LineChart", "Monthly revenue trend", SQL_SALES_TREND)],
                }
            )
            return "최근 12개월 매출 추이입니다.", artifact

        if any(k in text for k in ("지역", "region", "매출", "sales", "revenue")):
            artifact = sanitize_artifact(
                {
                    "artifact_id": _aid(),
                    "type": "dashboard",
                    "widgets": [_db_widget("BarTable", "Sales by region", SQL_REGION_SALES)],
                }
            )
            return "지역별 매출 순위입니다.", artifact
    except (QueryError, OSError, Exception):  # noqa: BLE001
        pass

    artifact = sanitize_artifact(_global_help_artifact())
    return "글로벌 sales DB 질문을 이해했습니다. 샘플 질문으로 위젯을 확인할 수 있습니다.", artifact


def _is_global_mode(connection_id: str | None, allowed_tables: set[str] | None) -> bool:
    if connection_id == "dbconn_global":
        return True
    if allowed_tables and "monthly_sales" in allowed_tables:
        return True
    return False


def run_mock_agent(
    message: str,
    *,
    db_url: str | None = None,
    allowed_tables: set[str] | None = None,
    connection_id: str | None = None,
) -> tuple[str, dict[str, Any]]:
    global _active_db_url, _active_tables
    _active_db_url = db_url or DEMO_CUSTOMER_DATABASE_URL
    _active_tables = allowed_tables or SOC_TABLES

    if _is_global_mode(connection_id, _active_tables):
        return _run_global_mock(message)

    text = message.strip()
    lower = text.lower()

    try:
        if "보고서" in text or "report" in lower or " soc" in f" {lower}" or lower.startswith("soc"):
            artifact = sanitize_artifact(_report_artifact())
            return "SOC 보안 현황을 보고서 형태로 정리했습니다.", artifact

        if any(k in text for k in ("유형", "비중", "pie")) or ("방법" in text and "조치" not in text and "공격" not in text):
            artifact = sanitize_artifact(_method_pie_artifact())
            return "최근 90일 공격 유형별 비중입니다.", artifact

        if "심각도" in text or "severity" in lower:
            artifact = sanitize_artifact(_severity_artifact())
            return "최근 30일 심각도별 공격 현황입니다.", artifact

        if any(k in text for k in ("추이", "7일", "트렌드", "trend")):
            artifact = sanitize_artifact(_trend_artifact())
            return "최근 7일 일별 공격 추이입니다.", artifact

        if any(k in text for k in ("취약점", "cve", "vulnerability")):
            artifact = sanitize_artifact(_vuln_artifact())
            return "미해결 취약점 목록입니다.", artifact

        if any(k in text for k in ("차단", "blocked")) or (" ip" in f" {lower}"):
            artifact = sanitize_artifact(_blocked_artifact())
            return "차단된 IP 목록과 차단 사유입니다.", artifact

        if any(k in text for k in ("자산", "위험")) or ("서버" in text and "공격" not in text):
            artifact = sanitize_artifact(_asset_risk_artifact())
            return "자산별 공격 빈도와 위험도 순위입니다.", artifact

        if "공격" in text or "attack" in lower:
            artifact = sanitize_artifact(_attack_artifact())
            return "지난달 공격 이벤트를 서버별로 집계했습니다. 차트·순위·해결 방안을 확인하세요.", artifact

        if "인시던트" in text or "incident" in lower:
            artifact = sanitize_artifact(
                {
                    "artifact_id": _aid(),
                    "type": "dashboard",
                    "widgets": [_db_widget("DataTable", "인시던트", SQL_INCIDENTS)],
                }
            )
            return "최근 보안 인시던트 목록입니다.", artifact

    except (QueryError, OSError, Exception):  # noqa: BLE001
        pass

    artifact = sanitize_artifact(_help_artifact())
    return "질문을 이해했습니다. 데모용 SOC 샘플 질문으로 위젯을 확인할 수 있습니다.", artifact
