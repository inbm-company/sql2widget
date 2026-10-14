import pytest

from app import agent_service, config, data_agent, schema_linking as linking
from app.query import QueryError

ALLOWED = {f"table_{i}" for i in range(30)} | {"orders", "customers"}


def match(*sqls):
    return {"question": "q", "similarity": 0.9,
            "plan": {"widgets": [{"component": "DataTable", "title": "t", "sql": sql} for sql in sqls]}}








def test_cte_names_and_unpermitted_tables_are_dropped():
    sql = "WITH recent AS (SELECT * FROM orders) SELECT * FROM recent JOIN secrets ON 1=1"
    assert linking.link_from_matches([match(sql)], ALLOWED)["tables"] == {"orders"}




def run_with(monkeypatch, matches, allowed=ALLOWED):
    plan_schemas = []
    monkeypatch.setattr(agent_service, "_resolve_db_url", lambda *a, **k: ("db", "conn", set(allowed)))
    monkeypatch.setattr(agent_service, "_schema_text_for_connection",
                        lambda tenant, conn, tables: "FULL" if tables == set(allowed) else f"LINKED:{sorted(tables)}")
    monkeypatch.setattr(agent_service.question_similarity, "search_questions",
                        lambda *a, **k: {"status": "matched" if matches else "no_match", "matches": matches})
    monkeypatch.setattr(agent_service, "decide_route",
                        lambda *a, **k: {"route": "data_query", "source": "similarity", "clarify": False})

    def plan(*args, **kwargs):
        plan_schemas.append(kwargs["schema"])
        column = "missing" if len(plan_schemas) == 1 else "id"
        return {"summary": "주문 조회", "queries": [
            {"sql": f"SELECT {column} FROM orders", "title": "주문", "purpose": "주문 조회"}]}, {"provider": "gemini"}

    monkeypatch.setattr(data_agent, "generate_sql", plan)
    return plan_schemas




def test_failure_retries_with_full_schema(monkeypatch):
    schemas = run_with(monkeypatch, [match("SELECT * FROM orders")])
    outcomes = iter([QueryError("no such column"), [{"id": 1}]])

    def execute(*args, **kwargs):
        outcome = next(outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        kwargs["result_metadata"].update(columns=[{"name": "id", "type": "numeric"}], row_count=1)
        return outcome

    actions = iter([
        {"action": "generate_sql"},
        {"action": "execute_sql", "query_id": "query_1"},
        {"action": "generate_sql", "query_id": "query_1"},
        {"action": "execute_sql", "query_id": "query_1"},
        {"action": "select_widgets", "query_id": "query_1"},
        {"action": "create_widget", "widget_id": "widget_1"},
        {"action": "finish"},
    ])
    monkeypatch.setattr(data_agent, "choose_data_action",
                        lambda *a, **k: {"request": "q", "reason": "", **next(actions)})
    monkeypatch.setattr(data_agent, "execute_readonly", execute)
    monkeypatch.setattr(data_agent, "select_widgets", lambda *a, **k: ([
        {"component": "DataTable", "title": "주문", "props": {"column_map": {}}}], {"provider": "gemini"}))
    monkeypatch.setattr(agent_service, "evaluate", lambda *a, **k: {"verdict": "done", "reason": "조회 완료"})
    _, artifact, meta = agent_service.run_agent("q", tenant_id="t", user_id="u", forced_route="data_query")
    assert schemas == ["LINKED:['orders']", "FULL"]
    assert meta["schema_link"]["escalated_to_full"] is True and meta["retried"]
    assert artifact["widgets"][0]["sql"] == "SELECT id FROM orders"
    assert meta["sql_generation"]["repairs"] == 1
    assert meta["loop_stop"] == "done"

