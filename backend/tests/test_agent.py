import json

from app.agent import GLOBAL_SAMPLE_QUESTIONS, SAMPLE_QUESTIONS, run_mock_agent
from app.config import ALLOWED_COMPONENTS, STAGE_GLOBAL_DATABASE_URL


def test_attack_question_components():
    summary, artifact = run_mock_agent(
        "지난달 공격당한 서버들의 공격 순위, 방법, 해결 방안을 보여줘."
    )
    assert summary
    assert artifact["type"] == "dashboard"
    comps = {w["component"] for w in artifact["widgets"]}
    assert "BarTable" in comps
    assert comps <= ALLOWED_COMPONENTS
    chart = next(w for w in artifact["widgets"] if w["component"] == "BarTable")
    assert "SELECT" in (chart.get("sql") or "")
    assert chart["props"].get("categories")
    assert chart["props"].get("rows")


def test_method_pie_question():
    _, artifact = run_mock_agent("공격 유형별 비중을 보여줘.")
    assert artifact["type"] == "dashboard"
    comps = {w["component"] for w in artifact["widgets"]}
    assert "PieTable" in comps


def test_severity_question():
    _, artifact = run_mock_agent("심각도별 공격 현황을 보여줘.")
    comps = {w["component"] for w in artifact["widgets"]}
    assert "KpiStat" in comps
    assert "DataTable" in comps


def test_attack_includes_bar_table():
    _, artifact = run_mock_agent(
        "지난달 공격당한 서버들의 공격 순위, 방법, 해결 방안을 보여줘."
    )
    comps = {w["component"] for w in artifact["widgets"]}
    assert "BarTable" in comps
    assert "BarChart" not in comps
    assert "RankList" not in comps


def test_report_question():
    _, artifact = run_mock_agent("SOC 보안 현황을 보고서 형태로 만들어줘.")
    assert artifact["type"] == "report"
    assert any(w["component"] == "MarkdownBlock" for w in artifact["widgets"])


def test_vulnerability_question():
    _, artifact = run_mock_agent("열린 취약점 목록을 보여줘.")
    assert any(w["component"] == "DataTable" for w in artifact["widgets"])


def test_sample_questions_list():
    assert len(SAMPLE_QUESTIONS) >= 8


def test_global_region_sales_json_serializable():
    summary, artifact = run_mock_agent(
        "지역별 매출 순위를 보여줘.",
        db_url=STAGE_GLOBAL_DATABASE_URL,
        allowed_tables={"regions", "products", "monthly_sales"},
        connection_id="dbconn_global",
    )
    assert summary
    assert artifact["widgets"]
    json.dumps(artifact)  # Decimal must already be converted


def test_global_sample_questions_all_produce_widgets():
    for q in GLOBAL_SAMPLE_QUESTIONS:
        summary, artifact = run_mock_agent(
            q,
            db_url=STAGE_GLOBAL_DATABASE_URL,
            allowed_tables={"regions", "products", "monthly_sales"},
            connection_id="dbconn_global",
        )
        assert summary
        assert artifact.get("widgets")
        json.dumps(artifact)
