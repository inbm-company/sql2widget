import secrets
from urllib.parse import urlparse

import psycopg
from psycopg.rows import dict_row

from app.crypto import decrypt_secret, encrypt_secret
from app.db import fetch_all, fetch_one, get_conn


def _id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(8)}"


def list_connections(tenant_id: str) -> list[dict]:
    rows = fetch_all(
        """
        SELECT id, name, host, port, database_name, username, sslmode, created_at
        FROM database_connections
        WHERE tenant_id = %s
        ORDER BY created_at ASC
        """,
        (tenant_id,),
    )
    return rows


def get_connection(connection_id: str, tenant_id: str) -> dict | None:
    return fetch_one(
        """
        SELECT *
        FROM database_connections
        WHERE id = %s AND tenant_id = %s
        """,
        (connection_id, tenant_id),
    )


def connection_url(row: dict) -> str:
    password = decrypt_secret(row["password_encrypted"])
    user = row["username"]
    host = row["host"]
    port = row["port"]
    db = row["database_name"]
    sslmode = row.get("sslmode") or "prefer"
    return f"postgresql://{user}:{password}@{host}:{port}/{db}?sslmode={sslmode}"


def create_connection(
    *,
    tenant_id: str,
    name: str,
    host: str,
    port: int,
    database_name: str,
    username: str,
    password: str,
    created_by: str | None,
    sslmode: str = "prefer",
    connection_id: str | None = None,
) -> dict:
    cid = connection_id or _id("dbconn")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO database_connections (
                    id, tenant_id, name, host, port, database_name,
                    username, password_encrypted, sslmode, created_by
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    host = EXCLUDED.host,
                    port = EXCLUDED.port,
                    database_name = EXCLUDED.database_name,
                    username = EXCLUDED.username,
                    password_encrypted = EXCLUDED.password_encrypted,
                    sslmode = EXCLUDED.sslmode
                RETURNING id, name, host, port, database_name, username, sslmode, created_at
                """,
                (
                    cid,
                    tenant_id,
                    name,
                    host,
                    port,
                    database_name,
                    username,
                    encrypt_secret(password),
                    sslmode,
                    created_by,
                ),
            )
            return cur.fetchone()


def upsert_from_url(
    *,
    tenant_id: str,
    name: str,
    url: str,
    created_by: str | None,
    connection_id: str = "dbconn_demo",
) -> dict:
    parsed = urlparse(url)
    return create_connection(
        tenant_id=tenant_id,
        name=name,
        host=parsed.hostname or "localhost",
        port=parsed.port or 5432,
        database_name=(parsed.path or "/").lstrip("/") or "postgres",
        username=parsed.username or "postgres",
        password=parsed.password or "",
        created_by=created_by,
        connection_id=connection_id,
    )


def list_table_permissions(tenant_id: str, connection_id: str) -> list[dict]:
    return fetch_all(
        """
        SELECT id, connection_id, role, schema_name, table_name
        FROM table_permissions
        WHERE tenant_id = %s AND connection_id = %s
        ORDER BY role, schema_name, table_name
        """,
        (tenant_id, connection_id),
    )


def replace_table_permissions(
    *,
    tenant_id: str,
    connection_id: str,
    role: str,
    tables: list[dict],
) -> list[dict]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM table_permissions
                WHERE tenant_id = %s AND connection_id = %s AND role = %s
                """,
                (tenant_id, connection_id, role),
            )
            for t in tables:
                cur.execute(
                    """
                    INSERT INTO table_permissions (
                        id, tenant_id, connection_id, role, schema_name, table_name
                    ) VALUES (%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        _id("tperm"),
                        tenant_id,
                        connection_id,
                        role,
                        t.get("schema_name") or "public",
                        t["table_name"],
                    ),
                )
    return list_table_permissions(tenant_id, connection_id)


def allowed_tables_for_role(tenant_id: str, connection_id: str, role: str) -> set[str]:
    rows = fetch_all(
        """
        SELECT table_name FROM table_permissions
        WHERE tenant_id = %s AND connection_id = %s AND role = %s
        """,
        (tenant_id, connection_id, role),
    )
    return {r["table_name"] for r in rows}


def schema_metadata(row: dict, allowed_tables: set[str]) -> dict:
    """Read only permitted PostgreSQL schema metadata; never inspect row values."""
    names = sorted({name.lower() for name in allowed_tables})
    if not names:
        return {"tables": [], "foreign_keys": []}

    url = connection_url(row)
    with psycopg.connect(url, row_factory=dict_row) as conn:
        conn.read_only = True
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_schema, table_name, column_name, data_type, udt_name,
                       is_nullable, ordinal_position
                FROM information_schema.columns
                WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
                  AND lower(table_name) = ANY(%s)
                ORDER BY table_schema, table_name, ordinal_position
                """,
                (names,),
            )
            columns = cur.fetchall()
            cur.execute(
                """
                SELECT kcu.table_schema, kcu.table_name, kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                 AND tc.table_schema = kcu.table_schema
                 AND tc.table_name = kcu.table_name
                WHERE tc.constraint_type = 'PRIMARY KEY'
                  AND tc.table_schema NOT IN ('pg_catalog', 'information_schema')
                  AND lower(tc.table_name) = ANY(%s)
                ORDER BY kcu.table_schema, kcu.table_name, kcu.ordinal_position
                """,
                (names,),
            )
            primary_keys = cur.fetchall()
            cur.execute(
                """
                SELECT tc.table_schema, tc.table_name, kcu.column_name,
                       ccu.table_schema AS foreign_table_schema,
                       ccu.table_name AS foreign_table_name,
                       ccu.column_name AS foreign_column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                 AND tc.table_schema = kcu.table_schema
                 AND tc.table_name = kcu.table_name
                JOIN information_schema.constraint_column_usage ccu
                  ON ccu.constraint_name = tc.constraint_name
                 AND ccu.constraint_schema = tc.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_schema NOT IN ('pg_catalog', 'information_schema')
                  AND lower(tc.table_name) = ANY(%s)
                ORDER BY tc.table_schema, tc.table_name, kcu.ordinal_position
                """,
                (names,),
            )
            foreign_keys = cur.fetchall()

    primary_key_columns = {
        (item["table_schema"], item["table_name"], item["column_name"])
        for item in primary_keys
    }
    grouped: dict[tuple[str, str], list[dict]] = {}
    for column in columns:
        key = (column["table_schema"], column["table_name"])
        grouped.setdefault(key, []).append(
            {
                "name": column["column_name"],
                "type": column["data_type"],
                "udt_name": column["udt_name"],
                "nullable": column["is_nullable"] == "YES",
                "primary_key": (*key, column["column_name"]) in primary_key_columns,
            }
        )
    return {
        "tables": [
            {"schema": schema, "name": name, "columns": table_columns}
            for (schema, name), table_columns in grouped.items()
        ],
        "foreign_keys": [dict(item) for item in foreign_keys],
    }


def format_schema_context(metadata: dict) -> str:
    """Compact, deterministic schema-only text safe to send to an LLM."""
    tables = metadata.get("tables") or []
    if not tables:
        return "No permitted tables are available for this connection."

    lines = [
        "PostgreSQL schema for the selected connection.",
        "Use only these permitted tables and columns. Do not query other tables.",
        "",
        "Tables:",
    ]
    for table in tables:
        lines.append(f"- {table['schema']}.{table['name']}")
        for column in table["columns"]:
            suffix = []
            if column["primary_key"]:
                suffix.append("PK")
            if not column["nullable"]:
                suffix.append("NOT NULL")
            qualifier = f" [{', '.join(suffix)}]" if suffix else ""
            lines.append(f"  - {column['name']}: {column['type']}{qualifier}")

    foreign_keys = metadata.get("foreign_keys") or []
    if foreign_keys:
        lines.extend(["", "Foreign keys:"])
        for fk in foreign_keys:
            lines.append(
                "- {table_schema}.{table_name}.{column_name} -> "
                "{foreign_table_schema}.{foreign_table_name}.{foreign_column_name}".format(**fk)
            )
    return "\n".join(lines)


def schema_context_for_connection(row: dict, allowed_tables: set[str]) -> str:
    return format_schema_context(schema_metadata(row, allowed_tables))
