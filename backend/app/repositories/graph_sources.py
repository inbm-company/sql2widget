import secrets

from app.db import fetch_all, fetch_one, get_conn


SOURCE_COLUMNS = ("s.*, (SELECT count(*) FROM graph_source_files f WHERE f.source_id = s.id)::int AS file_count")


def list_sources(tenant_id: str, project_id: str) -> list[dict]:
    return fetch_all(
        f"SELECT {SOURCE_COLUMNS} FROM graph_sources s WHERE s.tenant_id = %s AND s.project_id = %s ORDER BY s.created_at",
        (tenant_id, project_id),
    )


def get_source(source_id: str, tenant_id: str, project_id: str) -> dict | None:
    return fetch_one(
        f"SELECT {SOURCE_COLUMNS} FROM graph_sources s WHERE s.id = %s AND s.tenant_id = %s AND s.project_id = %s",
        (source_id, tenant_id, project_id),
    )


def get_files(source_id: str) -> dict[str, str]:
    rows = fetch_all("SELECT path, content FROM graph_source_files WHERE source_id = %s", (source_id,))
    return {row['path']: row['content'] for row in rows}


def _store_files(cur, source_id: str, files: dict[str, str]) -> None:
    cur.execute("DELETE FROM graph_source_files WHERE source_id = %s", (source_id,))
    cur.executemany("INSERT INTO graph_source_files (source_id, path, content) VALUES (%s, %s, %s)",
                    [(source_id, path, text) for path, text in files.items()])


def create_source(*, tenant_id: str, project_id: str, created_by: str, name: str, files: dict[str, str]) -> dict:
    source_id = f"gsource_{secrets.token_hex(8)}"
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO graph_sources (id, tenant_id, project_id, name, path, created_by) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (source_id, tenant_id, project_id, name, f"upload:{source_id}", created_by),
            )
            _store_files(cur, source_id, files)
    return get_source(source_id, tenant_id, project_id)


def replace_files(source_id: str, tenant_id: str, project_id: str, files: dict[str, str]) -> dict | None:
    """Swap the stored documents; the source must be ingested again to update the graph."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE graph_sources SET status = 'registered', error = NULL "
                "WHERE id = %s AND tenant_id = %s AND project_id = %s RETURNING id",
                (source_id, tenant_id, project_id),
            )
            if not cur.fetchone():
                return None
            _store_files(cur, source_id, files)
    return get_source(source_id, tenant_id, project_id)


def mark_processing(source_id: str, tenant_id: str, project_id: str) -> None:
    fetch_one(
        """
        UPDATE graph_sources SET status = 'processing', error = NULL
        WHERE id = %s AND tenant_id = %s AND project_id = %s RETURNING id
        """,
        (source_id, tenant_id, project_id),
    )


def mark_failed(source_id: str, tenant_id: str, project_id: str, error: str) -> None:
    fetch_one(
        """
        UPDATE graph_sources SET status = 'failed', error = %s
        WHERE id = %s AND tenant_id = %s AND project_id = %s RETURNING id
        """,
        (error, source_id, tenant_id, project_id),
    )


def mark_completed(source_id: str, tenant_id: str, project_id: str, counts: dict) -> dict:
    return fetch_one(
        """
        UPDATE graph_sources
        SET status = 'completed', error = NULL, last_ingested_at = now(),
            document_count = %s, chunk_count = %s, link_count = %s,
            skipped_count = %s, unresolved_link_count = %s
        WHERE id = %s AND tenant_id = %s AND project_id = %s RETURNING *
        """,
        (counts['document_count'], counts['chunk_count'], counts['link_count'],
         counts['skipped_count'], counts['unresolved_link_count'], source_id, tenant_id, project_id),
    )
