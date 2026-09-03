"""Read-only SQL validation and execution against customer DBs."""

from __future__ import annotations

import re
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|"
    r"COPY|CALL|DO|EXECUTE|MERGE|COMMENT|VACUUM|ANALYZE|REINDEX|CLUSTER|"
    r"REFRESH|SECURITY|SET\s+ROLE|SET\s+SESSION)\b",
    re.IGNORECASE,
)


class QueryError(Exception):
    pass


def jsonable(value: Any) -> Any:
    """Convert DB/driver values into JSON-serializable Python types."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        # Prefer int when the value is whole; otherwise float for charts/UI.
        if value == value.to_integral_value():
            return int(value)
        return float(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value).decode("utf-8", errors="replace")
    return str(value)


def validate_readonly_select(sql: str, allowed_tables: set[str] | None = None) -> str:
    text = (sql or "").strip().rstrip(";")
    if not text:
        raise QueryError("Empty SQL")
    if ";" in text:
        raise QueryError("Multiple statements are not allowed")
    if FORBIDDEN.search(text):
        raise QueryError("Only read-only SELECT is allowed")
    if not re.match(r"^(WITH|SELECT)\b", text, re.IGNORECASE | re.DOTALL):
        raise QueryError("SQL must start with SELECT or WITH")
    if re.search(r"\bFOR\s+(UPDATE|SHARE)\b", text, re.IGNORECASE):
        raise QueryError("Locking clauses are not allowed")
    if allowed_tables is not None:
        # naive table token check: FROM/JOIN identifiers
        refs = re.findall(
            r"\b(?:FROM|JOIN)\s+([a-zA-Z_][\w\.]*)",
            text,
            flags=re.IGNORECASE,
        )
        for ref in refs:
            name = ref.split(".")[-1].lower()
            allowed = {t.lower() for t in allowed_tables}
            if name not in allowed:
                raise QueryError(f"Table not permitted: {ref}")
    return text


def execute_readonly(
    database_url: str,
    sql: str,
    *,
    allowed_tables: set[str] | None = None,
    row_limit: int = 1000,
    timeout_seconds: int = 10,
) -> list[dict[str, Any]]:
    clean = validate_readonly_select(sql, allowed_tables=allowed_tables)
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        conn.read_only = True
        with conn.cursor() as cur:
            cur.execute(f"SET statement_timeout = '{int(timeout_seconds) * 1000}'")
            cur.execute(clean)
            rows = cur.fetchmany(row_limit)
            return [{k: jsonable(v) for k, v in row.items()} for row in rows]
