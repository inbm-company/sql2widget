from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app import graph_ingestion, graph_schema, graph_service as service, project_graph
from app.auth import get_current_user
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


def http(exc: service.GraphServiceError) -> HTTPException:
    return HTTPException(status_code=exc.status, detail=exc.message)


class UploadFile(BaseModel):
    path: str = Field(min_length=1, max_length=1000)
    text: str = Field(max_length=graph_ingestion.MAX_FILE_BYTES)


class GraphSourceIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    files: list[UploadFile] = Field(min_length=1, max_length=20000)


class GraphFilesIn(BaseModel):
    files: list[UploadFile] = Field(min_length=1, max_length=20000)


def validated_files(files: list[UploadFile]) -> tuple[dict[str, str], int]:
    """Filter the upload and run the same checks as ingestion, so bad input fails before storing."""
    try:
        kept, excluded = graph_ingestion.filter_upload([f.model_dump() for f in files])
        graph_ingestion.build_documents(kept)
    except graph_ingestion.GraphSourceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return kept, excluded


@router.get('/graph-sources')
def list_sources(project_id: str, user=Depends(graph_admin)):
    return {'sources': repo.list_sources(user['tenant_id'], project_id),
            'supported_extensions': sorted(graph_ingestion.SUPPORTED_EXTENSIONS)}


@router.post('/graph-sources')
def register_source(project_id: str, body: GraphSourceIn, user=Depends(graph_admin)):
    if not body.name.strip():
        raise HTTPException(status_code=400, detail='이름을 입력하세요.')
    kept, excluded = validated_files(body.files)
    source = repo.create_source(tenant_id=user['tenant_id'], project_id=project_id,
                                created_by=user['id'], name=body.name.strip(), files=kept)
    return {**source, 'excluded_count': excluded}


@router.put('/graph-sources/{source_id}/files')
def replace_source_files(project_id: str, source_id: str, body: GraphFilesIn, user=Depends(graph_admin)):
    try:
        with service.source_lock(source_id):
            service.reject_while_extracting(service.get_source(source_id, user['tenant_id'], project_id))
            kept, excluded = validated_files(body.files)
            source = repo.replace_files(source_id, user['tenant_id'], project_id, kept)
            if not source:
                raise HTTPException(status_code=404, detail='등록된 데이터 소스를 찾을 수 없습니다.')
            return {**source, 'excluded_count': excluded}
    except service.GraphServiceError as exc:
        raise http(exc) from None


@router.post('/graph-sources/{source_id}/ingest')
def ingest_source(project_id: str, source_id: str, user=Depends(graph_admin)):
    try:
        return service.ingest(source_id, user['tenant_id'], project_id)
    except service.GraphServiceError as exc:
        raise http(exc) from None


class SchemaProposeIn(BaseModel):
    instruction: str = Field(default='', max_length=1000)


class SchemaIn(BaseModel):
    schema_: dict = Field(alias='schema')


def llm_settings(request: Request) -> dict:
    """AI connection of the calling browser, sent the same way as for chat."""
    return {'provider': request.headers.get('X-LLM-Provider', ''), 'api_key': request.headers.get('X-LLM-API-Key', ''),
            'model': request.headers.get('X-LLM-Model', ''), 'base_url': request.headers.get('X-LLM-Base-URL', '')}


@router.post('/graph-sources/{source_id}/schema/propose')
def propose_schema(project_id: str, source_id: str, body: SchemaProposeIn, request: Request,
                   user=Depends(graph_admin)):
    """LLM proposes an entity schema from the stored documents; with an instruction it revises the draft."""
    try:
        return service.propose_schema(source_id, user['tenant_id'], project_id, user,
                                      instruction=body.instruction, llm_settings=llm_settings(request))
    except service.GraphServiceError as exc:
        raise http(exc) from None


@router.put('/graph-sources/{source_id}/schema')
def edit_schema(project_id: str, source_id: str, body: SchemaIn, user=Depends(graph_admin)):
    """Store a schema edited by the user; it must be approved again."""
    try:
        service.get_source(source_id, user['tenant_id'], project_id)
        schema = graph_schema.validate_schema(body.schema_)
    except service.GraphServiceError as exc:
        raise http(exc) from None
    except graph_ingestion.GraphSourceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return repo.save_schema(source_id, user['tenant_id'], project_id, schema, 'proposed')


@router.post('/graph-sources/{source_id}/schema/approve')
def approve_schema(project_id: str, source_id: str, user=Depends(graph_admin)):
    try:
        return service.approve_schema(source_id, user['tenant_id'], project_id)
    except service.GraphServiceError as exc:
        raise http(exc) from None


@router.post('/graph-sources/{source_id}/extract')
def extract_entities(project_id: str, source_id: str, request: Request, user=Depends(graph_admin)):
    """Start the background job that extracts entities with the approved schema from the ingested chunks."""
    try:
        return service.start_extraction(source_id, user['tenant_id'], project_id, user,
                                        llm_settings=llm_settings(request))
    except service.GraphServiceError as exc:
        raise http(exc) from None


@router.post('/graph-sources/{source_id}/extract/cancel')
def cancel_extraction(project_id: str, source_id: str, user=Depends(graph_admin)):
    try:
        service.cancel_extraction(source_id, user['tenant_id'], project_id)
    except service.GraphServiceError as exc:
        raise http(exc) from None
    return {'cancelling': True}


@router.get('/graph-sources/{source_id}/entities')
def get_entities(project_id: str, source_id: str, limit: int = Query(default=500, ge=1, le=2000),
                 user=Depends(graph_admin)):
    try:
        service.get_source(source_id, user['tenant_id'], project_id)
        return project_graph.source_entities(user['tenant_id'], project_id, source_id, limit)
    except service.GraphServiceError as exc:
        raise http(exc) from None
    except graph_ingestion.GraphSourceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from None


@router.get('/graph/entities')
def get_project_entities(project_id: str, limit: int = Query(default=500, ge=1, le=2000),
                         user=Depends(project_user)):
    """Active entities and relations of every source in the project (read-only, viewers included)."""
    sources = repo.list_sources(user['tenant_id'], project_id)
    try:
        return project_graph.project_entities(user['tenant_id'], project_id, [s['id'] for s in sources], limit)
    except graph_ingestion.GraphSourceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from None


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
