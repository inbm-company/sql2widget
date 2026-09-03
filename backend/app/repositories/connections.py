import secrets
from urllib.parse import urlparse

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
