"""Explanation content stays in the message body, alongside data widgets."""

from types import SimpleNamespace

import pytest

from app import agent_service


def test_schema_explanation_returns_full_body_and_preserves_context(monkeypatch):
    calls = []
    body = "## orders\n\n| 컬럼 | 설명 |\n| --- | --- |\n| id | 주문 ID |"
    history = [{"role": "user", "content": "orders 구조는?"}]
    monkeypatch.setattr(agent_service, "json_with_llm", lambda hint, content, **kwargs:
        calls.append(content) or {"result": {"summary": "요약", "markdown": f"  {body}  "},
                                 "provider": "openai", "model": "test-model"})
    monkeypatch.setattr(agent_service, "execute_readonly", lambda *a, **k: pytest.fail("no SQL"))
    content, artifact, meta = agent_service._answer_schema(
        "그 컬럼은?", "orders(id integer)", {}, {}, history=history)
    assert content == body
    assert artifact == {"type": "answer", "widgets": []}
    assert calls == [{"question": "그 컬럼은?", "schema": "orders(id integer)", "history": history}]
    assert meta == {"provider": "openai", "model": "test-model"}


@pytest.mark.parametrize("answer", [None, [], "text", {}, {"markdown": " "}, {"markdown": 42}])
def test_schema_invalid_answer_still_raises_model_error(monkeypatch, answer):
    monkeypatch.setattr(agent_service, "json_with_llm", lambda *a, **k: {"result": answer})
    with pytest.raises(agent_service.AgentRunError, match="schema answer was empty"):
        agent_service._answer_schema("구조?", "orders(id)", {}, {})


def test_explanation_only_plan_has_no_widget_artifact(monkeypatch):
    monkeypatch.setattr(agent_service, "execute_readonly", lambda *a, **k: pytest.fail("no SQL"))
    content, artifact = agent_service._materialize_plan(
        {"summary": "구조 설명", "widgets": [{"component": "MarkdownBlock",
                                              "props": {"markdown": "orders.id는 주문 ID입니다."}}]},
        db_url="unused", allowed_tables={"orders"}, message="구조?", include_sources=False)
    assert content == "구조 설명\n\norders.id는 주문 ID입니다."
    assert artifact == {"type": "answer", "widgets": []}


def test_grounded_guidance_moves_to_body_and_preserves_query_and_sources(monkeypatch):
    sources = [{"doc_id": "d", "title": "공격 대응", "section": "차단", "excerpt": "출처의 대응 설명"}]
    monkeypatch.setattr(agent_service, "get_document_provider", lambda:
        SimpleNamespace(search=lambda *a, **k: sources))
    sql = "SELECT count(*) AS count FROM attack_events"
    content, artifact = agent_service._materialize_plan(
        {"summary": "공격 조회 결과", "widgets": [{"component": "DataTable", "sql": sql}]},
        db_url="unused", allowed_tables={"attack_events"}, message="공격 보여줘",
        connection_id="soc", prepared_results={sql: [{"count": 3}]})
    assert "출처의 대응 설명" in content
    assert [w["component"] for w in artifact["widgets"]] == ["DataTable", "SourceList"]
    assert artifact["widgets"][0]["query_ref"] == {"connection_id": "soc", "sql": sql}
    assert artifact["widgets"][1]["props"]["sources"][0]["title"] == "공격 대응"
    merged_body, merged_artifact = agent_service._merge_outputs([
        ("테이블 설명", {"type": "answer", "widgets": []}), (content, artifact)])
    assert merged_body.startswith("테이블 설명\n\n공격 조회 결과")
    assert merged_artifact["widgets"] == artifact["widgets"]
