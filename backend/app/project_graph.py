"""Read only the active graph whose sources belong to the authorized project."""

from neo4j.exceptions import Neo4jError, ServiceUnavailable

from app.graph_ingestion import GraphSourceError, graph_driver

DOCUMENT_SCOPE = '''
    MATCH (s:GraphSource)-[:HAS_DOCUMENT]->(d:GraphDocument)
    WHERE s.id IN $sources AND s.tenant_id = $tenant AND s.project_id = $project
      AND d.source_id = s.id AND d.tenant_id = $tenant AND d.project_id = $project
      AND d.active = true
'''
LINK_SCOPE = DOCUMENT_SCOPE + '''
    MATCH (d)-[r:LINKS_TO]->(target:GraphDocument)
    WHERE r.active = true AND r.tenant_id = $tenant AND r.project_id = $project
      AND target.active = true AND target.source_id IN $sources
      AND target.tenant_id = $tenant AND target.project_id = $project
'''
CHUNK_SCOPE = '''
    OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c:GraphChunk)
    WHERE c.active = true AND c.source_id = d.source_id
      AND c.tenant_id = $tenant AND c.project_id = $project
'''
MAX_LINKS = 1000
MAX_CONTENT_CHARS = 100000


def read_graph(tx, tenant_id: str, project_id: str, source_ids: list[str], limit: int) -> dict:
    parameters = {'tenant': tenant_id, 'project': project_id, 'sources': source_ids}
    totals = dict(tx.run(DOCUMENT_SCOPE + CHUNK_SCOPE + '''
        RETURN count(DISTINCT d) AS document_count, count(c) AS chunk_count
        ''', **parameters).single())
    totals['link_count'] = tx.run(LINK_SCOPE + ' RETURN count(r) AS n', **parameters).single()['n']
    totals['source_count'] = len(source_ids)
    nodes = [dict(record) for record in tx.run(DOCUMENT_SCOPE + CHUNK_SCOPE + '''
        RETURN d.id AS id, d.title AS title, d.path AS path, d.source_id AS source_id,
               s.name AS source_name, count(c) AS chunk_count
        ORDER BY title, id LIMIT $limit
        ''', limit=limit, **parameters)]
    ids = [node['id'] for node in nodes]
    links = [dict(record) for record in tx.run(LINK_SCOPE + '''
        AND d.id IN $ids AND target.id IN $ids
        RETURN DISTINCT d.id AS source, target.id AS target
        ORDER BY source, target LIMIT $link_limit
        ''', ids=ids, link_limit=MAX_LINKS + 1, **parameters)]
    return {'nodes': nodes, 'links': links[:MAX_LINKS], 'totals': totals,
            'truncated': totals['document_count'] > limit or len(links) > MAX_LINKS,
            'node_limit': limit, 'link_limit': MAX_LINKS}


def read_document(tx, tenant_id: str, project_id: str, source_ids: list[str], document_id: str) -> dict | None:
    record = tx.run(DOCUMENT_SCOPE + ' AND d.id = $document\n' + CHUNK_SCOPE + '''
        RETURN d.id AS id, d.title AS title, d.path AS path, s.name AS source_name,
               count(c) AS chunk_count, max(c.end) AS content_length,
               collect(CASE WHEN c.start < $content_limit
                   THEN {start: c.start, end: c.end, text: c.text} END) AS chunks
        ''', tenant=tenant_id, project=project_id, sources=source_ids,
        document=document_id, content_limit=MAX_CONTENT_CHARS).single()
    if not record:
        return None
    document = dict(record)
    parts = []
    end = 0
    for chunk in sorted(document.pop('chunks'), key=lambda item: item['start']):
        parts.append(chunk['text'][max(0, end - chunk['start']):])
        end = max(end, chunk['end'])
    document['content'] = ''.join(parts)[:MAX_CONTENT_CHARS]
    document['content_truncated'] = (document.pop('content_length') or 0) > MAX_CONTENT_CHARS
    return document


def project_graph(tenant_id: str, project_id: str, source_ids: list[str], limit: int) -> dict:
    if not source_ids:
        return {'nodes': [], 'links': [], 'totals': {'document_count': 0, 'chunk_count': 0,
                'source_count': 0, 'link_count': 0}, 'truncated': False,
                'node_limit': limit, 'link_limit': MAX_LINKS}
    return _read(read_graph, tenant_id, project_id, source_ids, limit)


def project_document(tenant_id: str, project_id: str, source_ids: list[str], document_id: str) -> dict | None:
    if not source_ids:
        return None
    return _read(read_document, tenant_id, project_id, source_ids, document_id)


def _read(reader, *args):
    try:
        with graph_driver().session(database='neo4j') as session:
            return session.execute_read(reader, *args)
    except (Neo4jError, ServiceUnavailable, OSError):
        raise GraphSourceError('Neo4j 그래프를 불러오지 못했습니다. 서버 상태와 접속 설정을 확인하세요.') from None


def tag_source_project(tx, source_id: str, tenant_id: str, project_id: str):
    tx.run('MATCH (s:GraphSource {id: $source, tenant_id: $tenant}) '
           'SET s.project_id = $project', source=source_id, tenant=tenant_id, project=project_id).consume()
    for label in ('GraphDocument', 'GraphChunk'):
        tx.run(f'MATCH (n:{label} {{source_id: $source, tenant_id: $tenant}}) '
               'SET n.project_id = $project', source=source_id, tenant=tenant_id, project=project_id).consume()
    tx.run('MATCH (d:GraphDocument {source_id: $source, tenant_id: $tenant})-[r:LINKS_TO]->'
           '(target:GraphDocument {source_id: $source, tenant_id: $tenant}) '
           'SET r.project_id = $project, r.tenant_id = $tenant',
           source=source_id, tenant=tenant_id, project=project_id).consume()


def assign_graph_project(source_id: str, tenant_id: str, project_id: str):
    try:
        with graph_driver().session(database='neo4j') as session:
            session.execute_write(tag_source_project, source_id, tenant_id, project_id)
    except (Neo4jError, ServiceUnavailable, OSError):
        raise GraphSourceError('기존 그래프의 프로젝트 연결에 실패했습니다. Neo4j 접속 상태를 확인하세요.') from None
