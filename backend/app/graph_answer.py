"""knowledge_qa: answer from the entities extracted from the project's documents, never by guessing."""

from __future__ import annotations

from collections import Counter
from typing import Any

from app import project_graph
from app.agent import sanitize_artifact
from app.graph_ingestion import GraphSourceError
from app.intent_router import ROUTE_LABELS
from app.llm import json_with_llm
from app.prompts import KNOWLEDGE_ANSWER_HINT, KNOWLEDGE_PICK_HINT
from app.repositories import graph_sources as repo

MAX_READ = 500  # entities read from Neo4j per question
MAX_FACTS = 40  # entities handed to the answering model


class KnowledgeError(RuntimeError):
    """The graph or the model failed; the caller reports it instead of answering."""


def has_entities(tenant_id: str, project_id: str | None) -> bool:
    """True when any document source of the project has extracted entities (cheap service-DB check)."""
    return bool(project_id) and any(s.get("entity_count") for s in repo.list_sources(tenant_id, project_id))


def _buttons(message: str, user: dict, *, offer_build: bool) -> list[dict[str, str]]:
    buttons = []
    if offer_build and user.get("role") == "admin":
        buttons.append({"label": "문서를 지식그래프로 만들기", "route": "graph_build", "message": message})
    buttons += [{"label": ROUTE_LABELS[name], "route": name, "message": message}
                for name in ("data_query", "schema_qa")]
    return buttons


def _nothing(summary: str, message: str, user: dict, meta: dict, *, offer_build: bool):
    return summary, {"type": "choices", "widgets": [], "choices": _buttons(message, user, offer_build=offer_build)}, meta


def _pick(message: str, graph: dict, llm_context: dict) -> tuple[list[dict], dict]:
    """Ask the model for relevant entity names; keep them plus their direct neighbours (names only chosen from the list)."""
    entities = graph["entities"]
    catalog = [{"type": e["type"], "name": e["name"], "description": e["properties"].get("description", "")}
               for e in entities]
    result = json_with_llm(KNOWLEDGE_PICK_HINT, {"question": message, "entities": catalog}, **llm_context)
    picked = (result.get("result") or {}).get("entities")
    if result.get("result") is None:
        raise KnowledgeError(f"{result.get('provider') or 'LLM'} request failed: {result.get('error')}")
    names = {n.lower() for n in picked if isinstance(n, str)} if isinstance(picked, list) else set()
    chosen = [e for e in entities if e["name"].lower() in names]
    ids = {e["id"] for e in chosen}
    near = []
    for rel in graph["relations"]:
        if rel["source"] in ids:
            near.append(rel["target"])
        elif rel["target"] in ids:
            near.append(rel["source"])
    by_id = {e["id"]: e for e in entities}
    extra = [by_id[i] for i in dict.fromkeys(near) if i in by_id and i not in ids]
    return (chosen + extra)[:MAX_FACTS], {"picked": len(chosen)}


def _evidence(entity: dict) -> list[str]:
    return [item["evidence"] for item in entity.get("evidence") or [] if item.get("evidence")]


def handle(message: str, *, user: dict, project_id: str | None, llm_context: dict[str, Any], meta: dict):
    """Return (summary, artifact, meta); raises KnowledgeError when the graph or model fails."""
    if not project_id:
        meta["knowledge"] = {"status": "no_project"}
        return _nothing("이 대화는 프로젝트에 속해 있지 않아 문서 그래프를 찾을 수 없어요.", message, user, meta,
                        offer_build=False)
    sources = repo.list_sources(user["tenant_id"], project_id)
    source_names = {source["id"]: source["name"] for source in sources}
    try:
        graph = project_graph.project_entities(user["tenant_id"], project_id, list(source_names), MAX_READ)
    except GraphSourceError as exc:
        raise KnowledgeError(str(exc)) from exc
    entities = graph["entities"]
    meta["knowledge"] = {
        "status": "no_entities" if not entities else "read",
        "entities_total": graph.get("total", len(entities)), "entities_read": len(entities),
        "relations_total": graph.get("relation_total", len(graph["relations"])),
        "relations_read": len(graph["relations"]),
        "truncated": graph["truncated"], "entities_in_prompt": 0, "relations_in_prompt": 0,
        "prompt_entities": [], "used": [], "used_entities": [], "used_relations": [],
    }
    if not entities:
        return _nothing("이 프로젝트에는 아직 문서에서 추출한 엔티티가 없어서 문서 내용으로 답할 수 없어요.",
                        message, user, meta, offer_build=True)

    facts_entities = entities
    if len(entities) > MAX_FACTS:
        facts_entities, picked = _pick(message, graph, llm_context)
        meta["knowledge"].update(picked)
        if not facts_entities:
            meta["knowledge"]["status"] = "no_match"
            return _nothing("질문과 관련된 내용을 문서 그래프에서 찾지 못했어요.", message, user, meta, offer_build=False)
    ids = {e["id"] for e in facts_entities}
    name_of = {e["id"]: e["name"] for e in entities}
    relations = [r for r in graph["relations"] if r["source"] in ids and r["target"] in ids]
    facts = {
        "type_counts": graph.get("type_counts") or dict(Counter(e["type"] for e in entities)),
        "truncated": graph["truncated"],
        "entities": [{"type": e["type"], "name": e["name"], "properties": e["properties"],
                      "evidence": _evidence(e)} for e in facts_entities],
        "relations": [{"from": name_of[r["source"]], "type": r["type"], "to": name_of[r["target"]],
                       "evidence": r["evidence"]} for r in relations],
    }
    result = json_with_llm(KNOWLEDGE_ANSWER_HINT, {"question": message, "facts": facts}, **llm_context)
    answer = result.get("result") or {}
    if not answer.get("markdown"):
        raise KnowledgeError(f"{result.get('provider') or 'LLM'} request failed: "
                             f"{result.get('error') or 'answer was empty'}")
    meta["provider"], meta["model"] = result.get("provider"), result.get("model")

    used_names = {n.lower() for n in answer.get("used") or [] if isinstance(n, str)}
    used = [e for e in facts_entities if e["name"].lower() in used_names]
    used_ids = {e["id"] for e in used}
    used_relations = [r for r in relations if r["source"] in used_ids and r["target"] in used_ids]

    def reference(entity: dict) -> dict:
        return {"id": entity["id"], "type": entity["type"], "name": entity["name"],
                "source": source_names.get(entity["source_id"], "")}

    meta["knowledge"].update(
        status="answered", entities_in_prompt=len(facts_entities), relations_in_prompt=len(relations),
        prompt_entities=[reference(e) for e in facts_entities], used=[e["name"] for e in used],
        used_entities=[{**reference(e), "evidence": e.get("evidence") or []} for e in used],
        used_relations=[{"from": name_of[r["source"]], "type": r["type"],
                         "to": name_of[r["target"]], "evidence": r.get("evidence")}
                        for r in used_relations],
    )

    widgets = [{"component": "MarkdownBlock", "title": "문서 기반 답변", "props": {"markdown": answer["markdown"]}}]
    if used:
        widgets.append({"component": "DataTable", "title": "근거 엔티티", "props": {
            "columns": [{"key": "type", "label": "타입"}, {"key": "name", "label": "이름"},
                        {"key": "description", "label": "설명"}, {"key": "source", "label": "문서 소스"}],
            "rows": [{"type": e["type"], "name": e["name"], "description": e["properties"].get("description", ""),
                      "source": source_names.get(e["source_id"], "")} for e in used]}})
        if used_relations:
            widgets.append({"component": "DataTable", "title": "관계", "props": {
                "columns": [{"key": "from", "label": "시작"}, {"key": "type", "label": "관계"},
                            {"key": "to", "label": "끝"}],
                "rows": [{"from": name_of[r["source"]], "type": r["type"], "to": name_of[r["target"]]}
                         for r in used_relations]}})
        cited = {(source_names.get(e["source_id"], ""), item.get("heading")) for e in used
                 for item in e.get("evidence") or [] if item.get("evidence")}
        if cited:
            widgets.append({"component": "SourceList", "title": "문서 출처", "props": {"sources": [
                {"title": title, "version": None, "section": section} for title, section in sorted(
                    cited, key=lambda pair: (pair[0], pair[1] or ""))]}})
    artifact = sanitize_artifact({"type": "report", "widgets": widgets})
    return answer.get("summary") or "문서 기반 답변입니다.", artifact, meta
