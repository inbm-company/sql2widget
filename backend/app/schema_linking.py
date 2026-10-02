"""Shrink the schema handed to the SQL planner when the permitted database is large."""

from __future__ import annotations

import re
from typing import Any

from app import config

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



def link_schema(message, matches, allowed_tables, **context):
    """Use expected questions or the full allowed schema; never read document graphs."""
    return link_from_matches(matches, allowed_tables)
