"""Chat flow that builds a source's entity graph: propose a schema, revise it by talking, approve, extract."""

from typing import Any

from app import graph_service as service
from app.repositories import graph_sources as repo

ROUTE = 'graph_build'


def _choice(label: str, kind: str, source_id: str) -> dict[str, Any]:
    return {'label': label, 'route': ROUTE, 'message': label, 'action': {'type': kind, 'source_id': source_id}}


def _reply(summary: str, meta: dict, *, source: dict | None = None, choices: list | None = None):
    """Text answer; with a source it also carries the card the chat UI renders."""
    artifact: dict[str, Any] = {'type': 'graph_flow' if source else 'choices', 'widgets': [],
                                'choices': choices or []}
    if source:
        meta['graph_build'] = {
            'source_name': source['name'], 'schema_status': source['schema_status'],
            'extract_status': source.get('extract_status'),
            'entity_count': source.get('entity_count', 0), 'relation_count': source.get('relation_count', 0),
        }
        artifact['graph'] = {
            'source_id': source['id'], 'source_name': source['name'],
            'schema_status': source['schema_status'], 'schema': source['schema_draft'],
        }
    return summary, artifact, meta


def _fresh(source_id: str, tenant_id: str, project_id: str) -> dict:
    return service.get_source(source_id, tenant_id, project_id)


def _propose(source: dict, user: dict, project_id: str, instruction: str, llm_settings: dict, meta: dict):
    updated = service.propose_schema(source['id'], user['tenant_id'], project_id, user,
                                     instruction=instruction, llm_settings=llm_settings)
    schema = updated['schema_draft']
    summary = (f"‘{updated['name']}’ 문서를 엔티티 타입 {len(schema['entity_types'])}개, "
               f"관계 {len(schema['relation_types'])}개로 나눠 봤어요. 확인하고 승인하거나, "
               "바꾸고 싶은 내용을 채팅으로 말씀해 주세요.")
    return _reply(summary, meta, source=updated, choices=[
        _choice('이 스키마로 승인하고 추출 시작', 'approve', source['id']),
        _choice('스키마를 처음부터 다시 제안받기', 'regenerate', source['id']),
    ])


def _extract(source: dict, user: dict, project_id: str, llm_settings: dict, meta: dict):
    """Ingest first when the documents are not in Neo4j yet, then start the background extraction."""
    if source['status'] != 'completed':
        source = service.ingest(source['id'], user['tenant_id'], project_id)
    started = service.start_extraction(source['id'], user['tenant_id'], project_id, user, llm_settings=llm_settings)
    return _reply('승인된 스키마로 엔티티 추출을 시작했어요. 진행 상황은 아래 카드에서 확인하고, 끝나면 Stage의 '
                  '그래프 보기에서 엔티티를 볼 수 있어요.', meta, source=started,
                  choices=[_choice('추출 취소', 'cancel', source['id'])])


def _talk(source: dict, message: str, user: dict, project_id: str, llm_settings: dict, meta: dict):
    """A free-text message: revise a pending proposal, otherwise report the state or start proposing."""
    if source['extract_status'] == 'running':
        return _reply('이 소스는 지금 엔티티를 추출하는 중이에요.', meta, source=source,
                      choices=[_choice('추출 취소', 'cancel', source['id'])])
    if source['schema_status'] == 'approved':
        done = source['extract_status'] == 'completed'
        summary = (f"이미 스키마가 승인되어 있고 엔티티 {source['entity_count']}개, 관계 {source['relation_count']}개를 "
                   "추출했어요." if done else "스키마는 승인되어 있어요. 추출을 시작할까요?")
        return _reply(summary, meta, source=source, choices=[
            _choice('다시 추출하기' if done else '추출 시작', 'extract', source['id']),
            _choice('스키마를 처음부터 다시 제안받기', 'regenerate', source['id'])])
    return _propose(source, user, project_id, message if source['schema_status'] == 'proposed' else '',
                    llm_settings, meta)


def handle(message: str, *, user: dict, project_id: str, llm_settings: dict, action: dict | None, meta: dict):
    """Return (summary, artifact, meta) for a graph_build chat turn; failures become readable answers."""
    meta['route'] = ROUTE
    if user.get('role') != 'admin':
        return _reply('문서 그래프 구성은 관리자만 할 수 있어요.', meta)
    action = action or {}
    sources = repo.list_sources(user['tenant_id'], project_id)
    if not sources:
        return _reply("이 프로젝트에 올린 문서가 없어요. DB 관리의 ‘Graph RAG 데이터 소스’에서 문서를 먼저 올려 주세요.", meta)
    source = next((s for s in sources if s['id'] == action.get('source_id')), None)
    if source is None and len(sources) == 1:
        source = sources[0]
    if source is None:
        return _reply('어느 문서 소스로 진행할까요?', meta, choices=[
            _choice(f"{s['name']} (문서 {s['file_count']}개)", 'select', s['id']) for s in sources])
    meta['graph_source_id'] = source['id']
    kind, tenant = action.get('type', 'talk'), user['tenant_id']
    try:
        if kind == 'approve':
            service.approve_schema(source['id'], tenant, project_id)
            return _extract(_fresh(source['id'], tenant, project_id), user, project_id, llm_settings, meta)
        if kind == 'extract':
            return _extract(source, user, project_id, llm_settings, meta)
        if kind == 'cancel':
            service.cancel_extraction(source['id'], tenant, project_id)
            return _reply('추출 취소를 요청했어요. 현재 조각을 마치고 멈추며 기존 결과는 바뀌지 않아요.', meta,
                          source=_fresh(source['id'], tenant, project_id))
        if kind == 'regenerate':
            return _propose(source, user, project_id, '', llm_settings, meta)
        return _talk(source, message, user, project_id, llm_settings, meta)
    except service.GraphServiceError as exc:
        return _reply(f'진행하지 못했어요: {exc.message}', meta, source=_fresh(source['id'], tenant, project_id))
