import pytest

from app import graph_answer as ga

ADMIN = {"id": "u", "tenant_id": "t", "role": "admin"}
VIEWER = {"id": "v", "tenant_id": "t", "role": "viewer"}
CTX = {"tenant_id": "t", "user_id": "u", "conversation_id": None}


def entity(i, kind="Table", name=None, **props):
    return {"id": f"e{i}", "type": kind, "name": name or f"item{i}", "source_id": "s1", "properties": props,
            "evidence": [{"evidence": f"{name or f'item{i}'} 설명 문장", "heading": "구조"}]}


def graph_of(entities, relations=(), truncated=False):
    return {"entities": entities, "relations": list(relations), "truncated": truncated}


@pytest.fixture
def world(monkeypatch):
    calls = []
    state = {"graph": graph_of([]), "pick": {"entities": []}, "answer": {}}
    monkeypatch.setattr(ga.repo, "list_sources", lambda tenant, project: [{"id": "s1", "name": "Northwind 문서"}])
    monkeypatch.setattr(ga.project_graph, "project_entities", lambda *a: state["graph"])

    def llm(hint, content, **kwargs):
        calls.append((hint, content))
        key = "pick" if hint is ga.KNOWLEDGE_PICK_HINT else "answer"
        value = state[key]
        return {"result": value, "error": "boom" if value is None else None, "provider": "gemini", "model": "m"}

    monkeypatch.setattr(ga, "json_with_llm", llm)
    state["calls"] = calls
    return state


def ask(**kwargs):
    return ga.handle("질문", user=kwargs.pop("user", ADMIN), project_id=kwargs.pop("project_id", "p"),
                     llm_context=CTX, meta={})


def test_no_project_or_no_entities_offers_choices_without_calling_the_model(world):
    summary, artifact, _ = ask(project_id=None)
    assert artifact["type"] == "choices" and "프로젝트" in summary
    summary, artifact, meta = ask()
    assert "추출한 엔티티가 없어서" in summary and world["calls"] == []
    assert [c["route"] for c in artifact["choices"]] == ["graph_build", "data_query", "schema_qa"]
    _, artifact, _ = ask(user=VIEWER)  # only admins may build the graph
    assert [c["route"] for c in artifact["choices"]] == ["data_query", "schema_qa"]


def test_small_graph_goes_straight_to_the_answer_and_builds_widgets_from_used_entities(world):
    orders, customers = entity(1, name="orders", description="주문"), entity(2, name="customers", description="고객")
    world["graph"] = graph_of([orders, customers, entity(3, "Column", "order_id")],
                              [{"source": "e1", "type": "REFERENCES_TABLE", "target": "e2", "evidence": "FK"}])
    world["answer"] = {"summary": "요약", "markdown": "orders는 customers를 참조합니다.", "used": ["Orders", "customers", "ghost"]}
    summary, artifact, meta = ask()
    assert len(world["calls"]) == 1  # no pick step for a small graph
    facts = world["calls"][0][1]["facts"]
    assert facts["type_counts"] == {"Table": 2, "Column": 1}
    assert {"from": "orders", "type": "REFERENCES_TABLE", "to": "customers", "evidence": "FK"} in facts["relations"]
    titles = [w["title"] for w in artifact["widgets"]]
    assert titles == ["문서 기반 답변", "근거 엔티티", "관계", "문서 출처"]
    rows = artifact["widgets"][1]["props"]["rows"]
    assert [r["name"] for r in rows] == ["orders", "customers"]  # unknown 'ghost' is dropped
    assert rows[0]["source"] == "Northwind 문서"
    assert artifact["widgets"][3]["props"]["sources"] == [
        {"title": "Northwind 문서", "version": None, "section": "구조"}]
    assert summary == "요약" and meta["knowledge"]["used"] == ["orders", "customers"]
    trace = meta["knowledge"]
    assert trace["status"] == "answered" and trace["entities_read"] == 3
    assert trace["relations_read"] == trace["relations_in_prompt"] == 1
    assert len(trace["prompt_entities"]) == 3
    assert [e["name"] for e in trace["used_entities"]] == ["orders", "customers"]
    assert trace["used_entities"][0]["source"] == "Northwind 문서"
    assert trace["used_entities"][0]["evidence"][0]["evidence"] == "orders 설명 문장"
    assert trace["used_relations"] == [{"from": "orders", "type": "REFERENCES_TABLE",
                                       "to": "customers", "evidence": "FK"}]


def test_answer_without_used_entities_is_text_only(world):
    world["graph"] = graph_of([entity(1)])
    world["answer"] = {"summary": "s", "markdown": "문서에 없습니다.", "used": []}
    _, artifact, _ = ask()
    assert [w["component"] for w in artifact["widgets"]] == ["MarkdownBlock"]


def test_large_graph_is_narrowed_to_picked_entities_and_their_neighbours(world):
    entities = [entity(i, name=f"t{i}") for i in range(ga.MAX_FACTS + 10)]
    world["graph"] = graph_of(entities, [{"source": "e0", "type": "REFERENCES_TABLE", "target": "e1", "evidence": "x"}])
    world["pick"] = {"entities": ["t0", "nope"]}
    world["answer"] = {"summary": "s", "markdown": "m", "used": ["t0"]}
    _, _, meta = ask()
    assert len(world["calls"]) == 2
    names = [e["name"] for e in world["calls"][1][1]["facts"]["entities"]]
    assert names == ["t0", "t1"]  # picked entity first, then its neighbour
    assert world["calls"][1][1]["facts"]["type_counts"] == {"Table": ga.MAX_FACTS + 10}
    assert meta["knowledge"]["picked"] == 1


def test_nothing_picked_says_so_without_answering(world):
    world["graph"] = graph_of([entity(i) for i in range(ga.MAX_FACTS + 1)])
    world["pick"] = {"entities": []}
    summary, artifact, meta = ask()
    assert "찾지 못했어요" in summary and artifact["type"] == "choices" and len(world["calls"]) == 1
    assert meta["knowledge"]["status"] == "no_match"
    assert meta["knowledge"]["entities_in_prompt"] == 0


def test_model_failure_is_raised_not_hidden(world):
    world["graph"] = graph_of([entity(1)])
    world["answer"] = None
    with pytest.raises(ga.KnowledgeError, match="boom"):
        ask()
    world["graph"] = graph_of([entity(i) for i in range(ga.MAX_FACTS + 1)])
    world["pick"] = None
    with pytest.raises(ga.KnowledgeError, match="boom"):
        ask()


def test_unreachable_graph_is_raised(monkeypatch, world):
    def down(*args):
        raise ga.GraphSourceError("Neo4j 그래프를 불러오지 못했습니다.")

    monkeypatch.setattr(ga.project_graph, "project_entities", down)
    with pytest.raises(ga.KnowledgeError, match="Neo4j"):
        ask()


def test_type_quotas_take_small_types_in_full_and_give_the_rest_to_the_largest():
    from app import project_graph

    counts = {'Column': 1038, 'Table': 170, 'View': 4, 'Schema': 3, 'Database': 1}
    quotas = project_graph._type_quotas(counts, 500)
    assert quotas == {'Database': 1, 'Schema': 3, 'View': 4, 'Table': 170, 'Column': 322}
    assert sum(quotas.values()) == 500
    assert project_graph._type_quotas({'Table': 10, 'Column': 20}, 500) == {'Table': 10, 'Column': 20}  # nothing cut
    assert project_graph._type_quotas({'A': 100, 'B': 100}, 50) == {'A': 25, 'B': 25}  # equal split when all are large


def test_answer_counts_come_from_exact_totals_not_from_the_truncated_sample(world):
    sample = [entity(i, "Column", f"c{i}") for i in range(3)]
    graph = graph_of(sample, truncated=True)
    graph.update(total=1216, type_counts={"Column": 1038, "Table": 170})
    world["graph"] = graph
    world["answer"] = {"summary": "s", "markdown": "m", "used": []}
    _, _, meta = ask()
    assert world["calls"][0][1]["facts"]["type_counts"] == {"Column": 1038, "Table": 170}
    assert meta["knowledge"]["entities_total"] == 1216
