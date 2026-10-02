import pytest

from app import agent_service, config, schema_linking as linking

ALLOWED = {f"table_{i}" for i in range(30)} | {"orders", "customers"}


def match(*sqls):
    return {"question": "q", "similarity": 0.9,
            "plan": {"widgets": [{"component": "DataTable", "title": "t", "sql": sql} for sql in sqls]}}


def test_referenced_tables_handles_joins_schema_prefix_and_quotes():
    sql = 'SELECT * FROM public.orders o JOIN "Customers" c ON c.id = o.cid JOIN table_1 USING (x)'
    assert linking.referenced_tables(sql) == {"orders", "customers", "table_1"}


def test_small_schema_keeps_everything():
    result = linking.link_from_matches([match("SELECT * FROM orders")], {"orders", "customers"})
    assert result == {"source": "full", "reason": "small_schema", "total": 2}


def test_large_schema_uses_only_tables_of_matched_questions():
    matches = [match("SELECT * FROM orders JOIN customers ON 1=1"), match("SELECT * FROM table_3")]
    result = linking.link_from_matches(matches, ALLOWED)
    assert result["source"] == "similarity" and result["total"] == 32
    assert result["tables"] == {"orders", "customers", "table_3"}


def test_cte_names_and_unpermitted_tables_are_dropped():
    sql = "WITH recent AS (SELECT * FROM orders) SELECT * FROM recent JOIN secrets ON 1=1"
    assert linking.link_from_matches([match(sql)], ALLOWED)["tables"] == {"orders"}


@pytest.mark.parametrize("matches", [[], [match("SELECT 1")], [match("SELECT * FROM secrets")]])
def test_no_usable_match_falls_back_to_full_with_reason(matches):
    result = linking.link_from_matches(matches, ALLOWED)
    assert (result["source"], result["reason"]) == ("full", "no_matched_tables")


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


def test_planner_gets_linked_schema_and_meta_says_so(monkeypatch):
    schemas = run_with(monkeypatch, [match("SELECT * FROM orders")])
    monkeypatch.setattr(agent_service, "_materialize_plan", lambda *a, **k: ("ok", {"widgets": []}))
    _, _, meta = agent_service.run_agent("q", tenant_id="t", user_id="u")
    assert schemas == ["LINKED:['orders']"]
    assert meta["schema_link"] == {"source": "similarity", "tables": ["orders"], "total": 32}


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


def test_no_match_uses_full_schema_and_records_reason(monkeypatch):
    schemas = run_with(monkeypatch, [])
    monkeypatch.setattr(agent_service, "_materialize_plan", lambda *a, **k: ("ok", {"widgets": []}))
    _, _, meta = agent_service.run_agent("q", tenant_id="t", user_id="u")
    assert schemas == ["FULL"]
    assert meta["schema_link"]["reason"] == "no_matched_tables"
