#!/usr/bin/env python3
"""Register the restored SKAX NMS database and allow its cinamon relations."""

import psycopg
from psycopg.rows import dict_row

from app.config import SKAX_NMS_DATABASE_URL
from app.repositories import connections as conn_repo


TENANT_ID = "tenant_demo"
USER_ID = "user_admin"
CONNECTION_ID = "dbconn_skax_nms"
SCHEMA_NAME = "cinamon"


def discover_relations() -> list[dict[str, str]]:
    with psycopg.connect(SKAX_NMS_DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT n.nspname AS schema_name, c.relname AS table_name
                FROM pg_catalog.pg_class c
                JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = %s
                  AND c.relkind IN ('r', 'p', 'v', 'm')
                ORDER BY c.relname
                """,
                (SCHEMA_NAME,),
            )
            return [dict(row) for row in cur.fetchall()]


def main() -> None:
    relations = discover_relations()
    if not relations:
        raise RuntimeError(f"No relations found in schema {SCHEMA_NAME}")

    conn_repo.upsert_from_url(
        tenant_id=TENANT_ID,
        name="SKAX NMS DB",
        url=SKAX_NMS_DATABASE_URL,
        created_by=USER_ID,
        connection_id=CONNECTION_ID,
    )
    for role in ("admin", "user", "viewer"):
        conn_repo.replace_table_permissions(
            tenant_id=TENANT_ID,
            connection_id=CONNECTION_ID,
            role=role,
            tables=relations,
        )
    print(f"seeded {CONNECTION_ID} + {len(relations)} relation permissions")


if __name__ == "__main__":
    main()
