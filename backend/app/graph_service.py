"""Graph source operations shared by the REST routes and the chat flow."""

from contextlib import contextmanager

from app import graph_extraction, graph_ingestion, graph_schema
from app.db import get_conn
from app.repositories import graph_sources as repo


class GraphServiceError(Exception):
    """A user-facing failure with the HTTP status the REST layer should use."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


@contextmanager
def source_lock(source_id: str):
    # Session locks also release if the process stops, allowing a safe retry.
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT pg_try_advisory_lock(hashtextextended(%s, 0)) AS locked', (source_id,))
            if not cur.fetchone()['locked']:
                raise GraphServiceError('이 소스는 이미 작업 중입니다.', 409)
            try:
                yield
            finally:
                cur.execute('SELECT pg_advisory_unlock(hashtextextended(%s, 0))', (source_id,))


def get_source(source_id: str, tenant_id: str, project_id: str) -> dict:
    source = repo.get_source(source_id, tenant_id, project_id)
    if not source:
        raise GraphServiceError('등록된 데이터 소스를 찾을 수 없습니다.', 404)
    return source


def reject_while_extracting(source: dict) -> None:
    if source.get('extract_status') == 'running':
        raise GraphServiceError('엔티티 추출이 진행 중입니다. 끝난 뒤 다시 시도하세요.', 409)


def ingest(source_id: str, tenant_id: str, project_id: str) -> dict:
    """Store the kept documents' text and chunks in Neo4j and record the outcome."""
    with source_lock(source_id):
        source = get_source(source_id, tenant_id, project_id)
        reject_while_extracting(source)
        try:
            repo.mark_processing(source_id, tenant_id, project_id)
            counts = graph_ingestion.ingest(source, repo.get_files(source_id))
            return repo.mark_completed(source_id, tenant_id, project_id, counts)
        except graph_ingestion.GraphSourceError as exc:
            repo.mark_failed(source_id, tenant_id, project_id, str(exc))
            raise GraphServiceError(str(exc), 400) from None
        except Exception:
            message = '적재 중 오류가 발생했습니다. 다시 실행하세요.'
            repo.mark_failed(source_id, tenant_id, project_id, message)
            raise GraphServiceError(message, 500) from None


def propose_schema(source_id: str, tenant_id: str, project_id: str, user: dict, *,
                   instruction: str, llm_settings: dict) -> dict:
    """Ask the LLM for a schema; with an instruction and an existing draft, revise that draft."""
    with source_lock(source_id):
        source = get_source(source_id, tenant_id, project_id)
        files = repo.get_files(source_id)
        if not files:
            raise GraphServiceError('올린 문서가 없습니다. 문서를 먼저 올려 주세요.')
        revise = bool(instruction.strip()) and source.get('schema_draft')
        try:
            schema = graph_schema.propose_schema(
                files, current=source['schema_draft'] if revise else None, instruction=instruction,
                tenant_id=tenant_id, user_id=user['id'], llm_settings=llm_settings)
        except graph_ingestion.GraphSourceError as exc:
            raise GraphServiceError(str(exc), 502) from None
        return repo.save_schema(source_id, tenant_id, project_id, schema, 'proposed')


def approve_schema(source_id: str, tenant_id: str, project_id: str) -> dict:
    get_source(source_id, tenant_id, project_id)
    approved = repo.approve_schema(source_id, tenant_id, project_id)
    if not approved:
        raise GraphServiceError('승인할 스키마 제안이 없습니다. 먼저 스키마를 제안받으세요.')
    return approved


def start_extraction(source_id: str, tenant_id: str, project_id: str, user: dict, *, llm_settings: dict) -> dict:
    """Start the background extraction job for an ingested source with an approved schema."""
    with source_lock(source_id):
        source = get_source(source_id, tenant_id, project_id)
        if source['schema_status'] != 'approved':
            raise GraphServiceError('승인된 스키마가 없습니다. 스키마를 제안받고 승인하세요.')
        if source['status'] != 'completed':
            raise GraphServiceError('먼저 문서를 적재하세요. 적재가 끝난 소스만 추출할 수 있습니다.')
        try:
            plan = graph_extraction.chunk_plan(source_id, repo.get_files(source_id))
        except graph_ingestion.GraphSourceError as exc:
            raise GraphServiceError(str(exc), 400) from None
        if not repo.start_extract(source_id, tenant_id, project_id, len(plan)):
            raise GraphServiceError('이 소스는 이미 추출 중입니다.', 409)
    graph_extraction.start_job(source, source['schema_draft'], plan, user_id=user['id'], llm_settings=llm_settings)
    return repo.get_source(source_id, tenant_id, project_id)


def cancel_extraction(source_id: str, tenant_id: str, project_id: str) -> None:
    get_source(source_id, tenant_id, project_id)
    if not graph_extraction.request_cancel(source_id):
        raise GraphServiceError('진행 중인 추출이 없습니다.', 409)
