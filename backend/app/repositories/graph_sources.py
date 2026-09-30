import secrets

from app.db import fetch_all, fetch_one


def list_sources(tenant_id: str) -> list[dict]:
    return fetch_all(
        "SELECT * FROM graph_sources WHERE tenant_id = %s ORDER BY created_at",
        (tenant_id,),
    )


def get_source(source_id: str, tenant_id: str) -> dict | None:
    return fetch_one(
        "SELECT * FROM graph_sources WHERE id = %s AND tenant_id = %s",
        (source_id, tenant_id),
    )


def register_source(*, tenant_id: str, created_by: str, name: str, path: str) -> dict:
    return fetch_one(
        """
        INSERT INTO graph_sources (id, tenant_id, name, path, created_by)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (tenant_id, path) DO UPDATE SET name = EXCLUDED.name
        RETURNING *
        """,
        (f"gsource_{secrets.token_hex(8)}", tenant_id, name, path, created_by),
    )


def mark_processing(source_id: str, tenant_id: str) -> None:
    fetch_one(
        """
        UPDATE graph_sources SET status = 'processing', error = NULL
        WHERE id = %s AND tenant_id = %s RETURNING id
        """,
        (source_id, tenant_id),
    )


def mark_failed(source_id: str, tenant_id: str, error: str) -> None:
    fetch_one(
        """
        UPDATE graph_sources SET status = 'failed', error = %s
        WHERE id = %s AND tenant_id = %s RETURNING id
        """,
        (error, source_id, tenant_id),
    )


def mark_completed(source_id: str, tenant_id: str, counts: dict) -> dict:
    return fetch_one(
        """
        UPDATE graph_sources
        SET status = 'completed', error = NULL, last_ingested_at = now(),
            document_count = %s, chunk_count = %s, link_count = %s,
            skipped_count = %s, unresolved_link_count = %s
        WHERE id = %s AND tenant_id = %s RETURNING *
        """,
        (counts['document_count'], counts['chunk_count'], counts['link_count'],
         counts['skipped_count'], counts['unresolved_link_count'], source_id, tenant_id),
    )
