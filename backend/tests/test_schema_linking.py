import pytest

from app import agent_service, config, schema_linking as linking

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
        plan_schemas.append(kwargs["schema_text"])
        return {"plan": {"widgets": []}, "provider": "gemini"}

    monkeypatch.setattr(agent_service, "plan_with_llm", plan)
    return plan_schemas




def test_failure_retries_with_full_schema(monkeypatch):
    schemas = run_with(monkeypatch, [match("SELECT * FROM orders")])
    outcomes = iter([ValueError("no such column"), ("ok", {"widgets": []})])

    def materialize(*args, **kwargs):
        outcome = next(outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(agent_service, "_materialize_plan", materialize)
    _, _, meta = agent_service.run_agent("q", tenant_id="t", user_id="u")
    assert schemas == ["LINKED:['orders']", "FULL"]
    assert meta["schema_link"]["escalated_to_full"] is True and meta["retried"]


