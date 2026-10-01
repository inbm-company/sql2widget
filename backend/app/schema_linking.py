"""Shrink the schema handed to the SQL planner when the permitted database is large."""

from __future__ import annotations

import re
from typing import Any

from app import config, project_graph
from app.graph_ingestion import GraphSourceError
from app.llm import json_with_llm
from app.prompts import TABLE_PICK_HINT

# Same FROM/JOIN reference rule as question_similarity validation, including quoted names.
TABLE_REF = re.compile(
    r'\b(?:FROM|JOIN)\s+((?:"[^"]+"|[a-zA-Z_]\w*)(?:\s*\.\s*(?:"[^"]+"|[a-zA-Z_]\w*))*)',
    flags=re.IGNORECASE,
)


def referenced_tables(sql: str) -> set[str]:
    """Return lower-case table names read by FROM/JOIN clauses (CTE names included)."""
    return {
        ref.split(".")[-1].strip().strip('"').replace('""', '"').lower()
        for ref in TABLE_REF.findall(sql or "")
    }


def link_from_matches(matches: list[dict[str, Any]], allowed_tables: set[str]) -> dict[str, Any]:
    """Pick the tables the matched expected questions use; otherwise keep the full schema.

    Returns {"source": "similarity", "tables", "total"} or {"source": "full", "reason", "total"}.
    The caller records the result in the response meta, so a full schema is never silent.
    """
    permitted = {name.lower() for name in allowed_tables}
    total = len(permitted)
    if total <= config.SCHEMA_LINK_MIN_TABLES:
        return {"source": "full", "reason": "small_schema", "total": total}
    used: set[str] = set()
    for match in matches:
        for widget in (match.get("plan") or {}).get("widgets") or []:
            used |= referenced_tables(widget.get("sql") or "")
    used &= permitted  # drops CTE names and anything the role may not read
    if not used:
        return {"source": "full", "reason": "no_matched_tables", "total": total}
    return {"source": "similarity", "tables": used, "total": total}


def _full(reason: str, total: int, error: str | None = None) -> dict[str, Any]:
    result = {"source": "full", "reason": reason, "total": total}
    if error:
        result["error"] = error
    return result


def link_from_graph(message: str, allowed_tables: set[str], *, tenant_id: str, project_id: str | None,
                    llm_context: dict[str, Any]) -> dict[str, Any]:
    """Let the chat model pick tables from the project's documented table list.

    The list is fixed Cypher output (name + description from the extracted `Table`
    entities); tables the documents do not mention stay selectable by name. The model
    can only choose names from that list, and the result is limited to permitted tables.
    """
    permitted = {name.lower() for name in allowed_tables}
    total = len(permitted)
    if not project_id:
        return _full("no_project", total)
    try:
        documented = project_graph.project_table_catalog(tenant_id, project_id)
    except GraphSourceError as exc:
        return _full("graph_unavailable", total, str(exc))
    catalog = [{"name": name, "description": documented.get(name, "")} for name in sorted(permitted)]
    documented_count = sum(bool(item["description"]) for item in catalog)
    if not any(item["description"] for item in catalog):
        return {**_full("no_documented_tables", total), "documented_tables": documented_count}
    result = json_with_llm(TABLE_PICK_HINT, {"question": message, "tables": catalog}, **llm_context)
    picked = (result.get("result") or {}).get("tables")
    chosen = {name.lower() for name in picked if isinstance(name, str)} & permitted if isinstance(picked, list) else set()
    if not chosen:
        return {**_full("no_tables_picked", total, result.get("error")),
                "documented_tables": documented_count}
    return {"source": "graph", "tables": chosen, "total": total,
            "documented_tables": documented_count,
            "selected_descriptions": [{"name": name, "description": documented.get(name, "")}
                                      for name in sorted(chosen)]}


def link_schema(message: str, matches: list[dict[str, Any]], allowed_tables: set[str], *, tenant_id: str,
                project_id: str | None, llm_context: dict[str, Any]) -> dict[str, Any]:
    """Similar questions first (no model call); the project's table documents when none apply."""
    link = link_from_matches(matches, allowed_tables)
    if link.get("reason") != "no_matched_tables":
        return link
    return link_from_graph(message, allowed_tables, tenant_id=tenant_id, project_id=project_id,
                           llm_context=llm_context)
