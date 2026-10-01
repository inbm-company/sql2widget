import secrets

from psycopg.types.json import Jsonb

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


def save_schema(source_id: str, tenant_id: str, project_id: str, schema: dict, status: str) -> dict | None:
    """Store the schema draft; any edit returns it to `proposed` until the user approves it again."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE graph_sources SET schema_draft = %s, schema_status = %s "
                "WHERE id = %s AND tenant_id = %s AND project_id = %s RETURNING id",
                (Jsonb(schema), status, source_id, tenant_id, project_id),
            )
            if not cur.fetchone():
                return None
    return get_source(source_id, tenant_id, project_id)


def approve_schema(source_id: str, tenant_id: str, project_id: str) -> dict | None:
    """Mark the stored draft as the confirmed schema; returns None when there is no draft to approve."""
    row = fetch_one(
        "UPDATE graph_sources SET schema_status = 'approved' "
        "WHERE id = %s AND tenant_id = %s AND project_id = %s AND schema_draft IS NOT NULL RETURNING id",
        (source_id, tenant_id, project_id),
    )
    return get_source(source_id, tenant_id, project_id) if row else None


def start_extract(source_id: str, tenant_id: str, project_id: str, total: int) -> bool:
    """Mark the extraction as running unless one already is; False means another job owns the source."""
    row = fetch_one(
        "UPDATE graph_sources SET extract_status = 'running', extract_error = NULL, extract_progress = %s "
        "WHERE id = %s AND tenant_id = %s AND project_id = %s AND extract_status <> 'running' RETURNING id",
        (Jsonb({'done': 0, 'total': total, 'failed': 0}), source_id, tenant_id, project_id),
    )
    return row is not None


def set_extract_progress(source_id: str, tenant_id: str, project_id: str, progress: dict) -> None:
    fetch_one(
        "UPDATE graph_sources SET extract_progress = %s WHERE id = %s AND tenant_id = %s AND project_id = %s RETURNING id",
        (Jsonb(progress), source_id, tenant_id, project_id),
    )


def finish_extract(source_id: str, tenant_id: str, project_id: str, *, status: str, error: str | None,
                   progress: dict, entity_count: int | None = None, relation_count: int | None = None) -> None:
    """Record the outcome; counts and the success time change only when the job completed."""
    fetch_one(
        """
        UPDATE graph_sources SET extract_status = %s, extract_error = %s, extract_progress = %s,
            entity_count = COALESCE(%s, entity_count), relation_count = COALESCE(%s, relation_count),
            last_extracted_at = CASE WHEN %s = 'completed' THEN now() ELSE last_extracted_at END
        WHERE id = %s AND tenant_id = %s AND project_id = %s RETURNING id
        """,
        (status, error, Jsonb(progress), entity_count, relation_count, status, source_id, tenant_id, project_id),
    )


def fail_interrupted_extractions() -> int:
    """At startup no job can still be running, so mark leftovers as failed to allow a retry."""
    rows = fetch_all(
        "UPDATE graph_sources SET extract_status = 'failed', "
        "extract_error = '서버가 재시작되어 추출이 중단되었습니다. 다시 실행하세요.' "
        "WHERE extract_status = 'running' RETURNING id"
    )
    return len(rows)
