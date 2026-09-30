from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app import graph_ingestion
from app.auth import get_current_user
from app.db import get_conn
from app.repositories import graph_sources as repo

router = APIRouter(prefix='/api/graph-sources', tags=['graph-sources'])


def graph_admin(user=Depends(get_current_user)):
    if user.get('role') != 'admin':
        raise HTTPException(status_code=403, detail='Admin only')
    return user


class GraphSourceIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    path: str = Field(min_length=1, max_length=2000)


@router.get('')
def list_sources(user=Depends(graph_admin)):
    return {'sources': repo.list_sources(user['tenant_id']),
            'shared_root': graph_ingestion.HOST_ROOT,
            'supported_extensions': sorted(graph_ingestion.SUPPORTED_EXTENSIONS)}


@router.post('')
def register_source(body: GraphSourceIn, user=Depends(graph_admin)):
    if not body.name.strip():
        raise HTTPException(status_code=400, detail='이름을 입력하세요.')
    try:
        _, path = graph_ingestion.resolve_source_path(body.path)
    except graph_ingestion.GraphSourceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return repo.register_source(tenant_id=user['tenant_id'], created_by=user['id'],
                                name=body.name.strip(), path=path)


@router.post('/{source_id}/ingest')
def ingest_source(source_id: str, user=Depends(graph_admin)):
    source = repo.get_source(source_id, user['tenant_id'])
    if not source:
        raise HTTPException(status_code=404, detail='등록된 데이터 소스를 찾을 수 없습니다.')
    # A session lock is released even if the process stops. A retry can recover
    # a persisted processing status without allowing two concurrent imports.
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT pg_try_advisory_lock(hashtextextended(%s, 0)) AS locked', (source_id,))
            if not cur.fetchone()['locked']:
                raise HTTPException(status_code=409, detail='이 소스는 이미 적재 중입니다.')
            try:
                repo.mark_processing(source_id, user['tenant_id'])
                counts = graph_ingestion.ingest(source)
                return repo.mark_completed(source_id, user['tenant_id'], counts)
            except graph_ingestion.GraphSourceError as exc:
                repo.mark_failed(source_id, user['tenant_id'], str(exc))
                raise HTTPException(status_code=400, detail=str(exc)) from None
            except Exception:
                message = '적재 중 오류가 발생했습니다. 저장된 경로를 확인하고 다시 실행하세요.'
                repo.mark_failed(source_id, user['tenant_id'], message)
                raise HTTPException(status_code=500, detail=message) from None
            finally:
                cur.execute('SELECT pg_advisory_unlock(hashtextextended(%s, 0))', (source_id,))
