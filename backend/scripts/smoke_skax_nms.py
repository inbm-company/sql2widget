#!/usr/bin/env python3
"""Verify the registered SKAX database and cinamon permissions without reading user rows."""

import json

from app.query import execute_readonly
from app.repositories import connections


def main() -> None:
    tenant_id = "tenant_demo"
    connection_id = "dbconn_skax_nms"
    row = connections.get_connection(connection_id, tenant_id)
    if row is None:
        raise RuntimeError("SKAX NMS connection is not registered")
    tables = execute_readonly(
        connections.connection_url(row),
        "SELECT c.relname AS name FROM pg_catalog.pg_class c "
        "JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'cinamon' AND c.relkind IN ('r', 'p', 'v', 'm')",
    )
    names = {table["name"] for table in tables}
    if not names:
        raise RuntimeError("SKAX NMS cinamon schema has no tables or views")
    roles = ("admin", "user", "viewer")
    for role in roles:
        permitted = connections.allowed_tables_for_role(tenant_id, connection_id, role)
        if not names.issubset(permitted):
            raise RuntimeError(f"SKAX NMS permissions are incomplete for {role}")
    print(json.dumps({"connection_id": connection_id, "table_count": len(names),
                      "roles": roles, "ok": True}))


if __name__ == "__main__":
    main()
