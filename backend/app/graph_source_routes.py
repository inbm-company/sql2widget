from contextlib import contextmanager

from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg.errors import UniqueViolation
from pydantic import BaseModel, Field

from app import graph_ingestion, project_graph
from app.auth import get_current_user
from app.db import get_conn
from app.repositories import graph_sources as repo, projects

router = APIRouter(prefix='/api/projects/{project_id}', tags=['graph-sources'])


def project_user(project_id: str, user=Depends(get_current_user)):
    if not projects.get_project(project_id, user['tenant_id'], user['id']):
        raise HTTPException(status_code=404, detail='프로젝트를 찾을 수 없습니다.')
    return user


def graph_admin(user=Depends(project_user)):
    if user.get('role') != 'admin':
        raise HTTPException(status_code=403, detail='Admin only')
    return user


@contextmanager
def source_lock(source_id):
    # Session locks also release if the process stops, allowing a safe retry.
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT pg_try_advisory_lock(hashtextextended(%s, 0)) AS locked', (source_id,))
            if not cur.fetchone()['locked']:
                raise HTTPException(status_code=409, detail='이 소스는 이미 작업 중입니다.')
            try:
                yield
            finally:
                cur.execute('SELECT pg_advisory_unlock(hashtextextended(%s, 0))', (source_id,))


class GraphSourceIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    path: str = Field(min_length=1, max_length=2000)


@router.get('/graph-sources')
def list_sources(project_id: str, user=Depends(graph_admin)):
    return {'sources': repo.list_sources(user['tenant_id'], project_id),
            'unassigned_sources': repo.list_unassigned(user['tenant_id'], user['id']),
            'shared_root': graph_ingestion.HOST_ROOT,
            'supported_extensions': sorted(graph_ingestion.SUPPORTED_EXTENSIONS)}


@router.post('/graph-sources')
def register_source(project_id: str, body: GraphSourceIn, user=Depends(graph_admin)):
    if not body.name.strip():
        raise HTTPException(status_code=400, detail='이름을 입력하세요.')
    try:
        _, path = graph_ingestion.resolve_source_path(body.path)
    except graph_ingestion.GraphSourceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return repo.register_source(tenant_id=user['tenant_id'], project_id=project_id,
                                created_by=user['id'], name=body.name.strip(), path=path)


@router.post('/graph-sources/{source_id}/assign')
def assign_source(project_id: str, source_id: str, user=Depends(graph_admin)):
    with source_lock(source_id):
        source = repo.get_unassigned(source_id, user['tenant_id'], user['id'])
        if not source:
            raise HTTPException(status_code=404, detail='연결할 기존 소스를 찾을 수 없습니다.')
        if any(item['path'] == source['path'] for item in repo.list_sources(user['tenant_id'], project_id)):
            raise HTTPException(status_code=409, detail='이 프로젝트에 같은 경로가 이미 등록되어 있습니다.')
        try:
            project_graph.assign_graph_project(source_id, user['tenant_id'], project_id)
            return repo.assign_source(source_id, user['tenant_id'], user['id'], project_id)
        except UniqueViolation:
            raise HTTPException(status_code=409, detail='이 프로젝트에 같은 경로가 이미 등록되어 있습니다.') from None
        except graph_ingestion.GraphSourceError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from None


@router.post('/graph-sources/{source_id}/ingest')
def ingest_source(project_id: str, source_id: str, user=Depends(graph_admin)):
    with source_lock(source_id):
        source = repo.get_source(source_id, user['tenant_id'], project_id)
        if not source:
            raise HTTPException(status_code=404, detail='등록된 데이터 소스를 찾을 수 없습니다.')
        try:
            repo.mark_processing(source_id, user['tenant_id'], project_id)
            counts = graph_ingestion.ingest(source)
            return repo.mark_completed(source_id, user['tenant_id'], project_id, counts)
        except graph_ingestion.GraphSourceError as exc:
            repo.mark_failed(source_id, user['tenant_id'], project_id, str(exc))
            raise HTTPException(status_code=400, detail=str(exc)) from None
        except Exception:
            message = '적재 중 오류가 발생했습니다. 저장된 경로를 확인하고 다시 실행하세요.'
            repo.mark_failed(source_id, user['tenant_id'], project_id, message)
            raise HTTPException(status_code=500, detail=message) from None


@router.get('/graph')
def get_graph(project_id: str, limit: int = Query(default=200, ge=1, le=500), user=Depends(project_user)):
    sources = repo.list_sources(user['tenant_id'], project_id)
    try:
        return project_graph.project_graph(user['tenant_id'], project_id, [s['id'] for s in sources], limit)
    except graph_ingestion.GraphSourceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from None


@router.get('/graph/documents/{document_id}')
def get_document(project_id: str, document_id: str, user=Depends(project_user)):
    sources = repo.list_sources(user['tenant_id'], project_id)
    try:
        document = project_graph.project_document(user['tenant_id'], project_id, [s['id'] for s in sources], document_id)
    except graph_ingestion.GraphSourceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from None
    if not document:
        raise HTTPException(status_code=404, detail='프로젝트의 문서를 찾을 수 없습니다.')
    return document
