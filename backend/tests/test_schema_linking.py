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
    assert meta["schema_link"]["reason"] == "no_project"


CTX = {"tenant_id": "t", "user_id": "u", "conversation_id": None}
DOCS = {"orders": "주문", "customers": "고객", "table_1": ""}


def graph(monkeypatch, documented=DOCS, picked=("Orders", "customers", "ghost"), error=None):
    calls = []
    monkeypatch.setattr(linking.project_graph, "project_table_catalog", lambda *a: documented)

    def pick(hint, content, **kwargs):
        calls.append(content)
        return {"result": {"tables": list(picked)} if picked is not None else None, "error": error}

    monkeypatch.setattr(linking, "json_with_llm", pick)
    return calls


def link_graph(**kwargs):
    return linking.link_from_graph("고객별 주문", ALLOWED, tenant_id="t", project_id="p", llm_context=CTX, **kwargs)


def test_graph_pick_is_limited_to_permitted_tables_and_sees_every_table(monkeypatch):
    calls = graph(monkeypatch)
    result = link_graph()
    assert result == {"source": "graph", "tables": {"orders", "customers"}, "total": 32,
                      "documented_tables": 2, "selected_descriptions": [
                          {"name": "customers", "description": "고객"},
                          {"name": "orders", "description": "주문"}]}
    names = [item["name"] for item in calls[0]["tables"]]
    assert names == sorted(name.lower() for name in ALLOWED)  # undocumented tables stay selectable
    assert {"name": "orders", "description": "주문"} in calls[0]["tables"]


def test_graph_without_project_or_descriptions_keeps_full_schema(monkeypatch):
    calls = graph(monkeypatch, documented={})
    assert link_graph()["reason"] == "no_documented_tables" and calls == []
    result = linking.link_from_graph("q", ALLOWED, tenant_id="t", project_id=None, llm_context=CTX)
    assert result["reason"] == "no_project"


def test_unreachable_graph_is_reported_not_hidden(monkeypatch):
    def down(*args):
        raise linking.GraphSourceError("Neo4j 그래프를 불러오지 못했습니다.")

    monkeypatch.setattr(linking.project_graph, "project_table_catalog", down)
    result = link_graph()
    assert (result["source"], result["reason"]) == ("full", "graph_unavailable") and "Neo4j" in result["error"]


@pytest.mark.parametrize("picked,error", [(None, "HTTP 429"), (["ghost"], None), ("orders", None)])
def test_unusable_pick_falls_back_to_full_with_reason(monkeypatch, picked, error):
    graph(monkeypatch, picked=picked, error=error)
    result = link_graph()
    assert (result["source"], result["reason"], result.get("error")) == ("full", "no_tables_picked", error)


def test_similar_questions_win_over_graph_and_skip_the_model(monkeypatch):
    calls = graph(monkeypatch)
    result = linking.link_schema("q", [match("SELECT * FROM orders")], ALLOWED, tenant_id="t",
                                 project_id="p", llm_context=CTX)
    assert result["source"] == "similarity" and calls == []


def test_small_schema_never_calls_the_model(monkeypatch):
    calls = graph(monkeypatch)
    result = linking.link_schema("q", [], {"orders"}, tenant_id="t", project_id="p", llm_context=CTX)
    assert result["reason"] == "small_schema" and calls == []


def test_run_agent_uses_graph_link_when_no_question_matches(monkeypatch):
    graph(monkeypatch)
    schemas = run_with(monkeypatch, [])
    monkeypatch.setattr(agent_service, "_materialize_plan", lambda *a, **k: ("ok", {"widgets": []}))
    _, _, meta = agent_service.run_agent("q", tenant_id="t", user_id="u", project_id="p")
    assert schemas == ["LINKED:['customers', 'orders']"]
    assert meta["schema_link"]["source"] == "graph"


def test_table_catalog_registers_bare_names_for_schema_qualified_entities():
    from app.project_graph import read_table_catalog

    class FakeTx:
        def run(self, *_args, **_kwargs):
            return [
                {"name": "cinamon.audit_log_web", "properties": '{"description": "접속 로그"}'},
                {"name": "etc.audit_log_web", "properties": "{}"},
                {"name": "Orders", "properties": '{"category": "매출"}'},
            ]

    catalog = read_table_catalog(FakeTx(), "t", "p")
    assert catalog["cinamon.audit_log_web"] == "접속 로그"
    assert catalog["audit_log_web"] == "접속 로그"
    assert catalog["orders"] == "매출"
