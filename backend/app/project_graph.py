"""Read only the active graph whose sources belong to the authorized project."""

import json

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


def _type_quotas(type_counts: dict[str, int], limit: int) -> dict[str, int]:
    """Split `limit` across entity types: smaller types are taken in full, larger ones share the remainder."""
    quotas, remaining = {}, limit
    for position, (kind, count) in enumerate(sorted(type_counts.items(), key=lambda item: (item[1], item[0]))):
        quotas[kind] = min(count, remaining // (len(type_counts) - position))
        remaining -= quotas[kind]
    return quotas


def read_entities(tx, tenant_id: str, project_id: str, source_ids: list[str], limit: int) -> dict:
    scope = {'tenant': tenant_id, 'project': project_id, 'sources': source_ids}
    # Exact totals first: the list below is only a sample, so counts must not be derived from it.
    type_counts = {r['type']: r['n'] for r in tx.run('''
        MATCH (e:Entity {tenant_id: $tenant, project_id: $project, active: true})
        WHERE e.source_id IN $sources
        RETURN e.type AS type, count(*) AS n ORDER BY n DESC, type
        ''', **scope)}
    relation_total = tx.run('''
        MATCH (a:Entity {tenant_id: $tenant, project_id: $project, active: true})-[r]->(b:Entity {active: true})
        WHERE a.source_id IN $sources AND r.active = true AND r.source_id IN $sources
        RETURN count(r) AS n
        ''', **scope).single()['n']
    # Every type gets a fair share of the sample (small types in full, the biggest type takes what is left),
    # best-connected entities first within a type. Cutting by type name would fill the sample with one type.
    entities = [dict(r) for r in tx.run('''
        MATCH (e:Entity {tenant_id: $tenant, project_id: $project, active: true})
        WHERE e.source_id IN $sources
        OPTIONAL MATCH (e)-[r]-(:Entity {active: true})
        WHERE r.active = true AND r.source_id IN $sources
        WITH e, count(r) AS degree
        ORDER BY degree DESC, e.name
        WITH e.type AS type, collect({e: e, degree: degree}) AS items
        UNWIND items[..toInteger($quota[type])] AS item
        WITH item.e AS e, item.degree AS degree
        OPTIONAL MATCH (e)-[f:FROM_CHUNK {active: true}]->(c:GraphChunk {active: true})
        WITH e, degree, collect(DISTINCT {evidence: f.evidence, heading: c.heading})[..3] AS evidence
        RETURN e.id AS id, e.type AS type, e.name AS name, e.props AS properties, e.source_id AS source_id,
               evidence, degree
        ORDER BY degree DESC, type, name
        ''', quota=_type_quotas(type_counts, limit), **scope)]
    for entity in entities:
        entity['properties'] = json.loads(entity['properties'] or '{}')
    ids = [e['id'] for e in entities]
    relations = [dict(r) for r in tx.run('''
        MATCH (a:Entity)-[r]->(b:Entity)
        WHERE a.id IN $ids AND b.id IN $ids AND r.active = true AND r.source_id IN $sources
        RETURN a.id AS source, type(r) AS type, b.id AS target, r.evidence AS evidence
        ORDER BY type, source, target LIMIT $limit
        ''', ids=ids, limit=limit * 4, **scope)]
    total = sum(type_counts.values())
    return {'entities': entities, 'relations': relations, 'truncated': total > len(entities), 'total': total,
            'type_counts': type_counts, 'relation_total': relation_total}


def read_table_catalog(tx, tenant_id: str, project_id: str) -> dict[str, str]:
    """Documented `Table` entities of the project: lowercase name (and bare name without schema) -> one-line description."""
    catalog: dict[str, str] = {}
    for record in tx.run('''
        MATCH (e:Entity {type: 'Table', tenant_id: $tenant, project_id: $project, active: true})
        RETURN e.name AS name, e.props AS properties ORDER BY name
        ''', tenant=tenant_id, project=project_id):
        properties = json.loads(record['properties'] or '{}')
        text = ' · '.join(str(properties[k]) for k in ('category', 'description') if properties.get(k))
        full_name = record['name'].lower()
        catalog.setdefault(full_name, text)
        # Permitted tables are bare names; the graph stores `schema.table`.
        bare_name = full_name.rsplit('.', 1)[-1].strip('"')
        if not catalog.get(bare_name):
            catalog[bare_name] = text
    return catalog


def project_table_catalog(tenant_id: str, project_id: str) -> dict[str, str]:
    return _read(read_table_catalog, tenant_id, project_id)


def source_entities(tenant_id: str, project_id: str, source_id: str, limit: int) -> dict:
    return _read(read_entities, tenant_id, project_id, [source_id], limit)


def project_entities(tenant_id: str, project_id: str, source_ids: list[str], limit: int) -> dict:
    if not source_ids:
        return {'entities': [], 'relations': [], 'truncated': False, 'total': 0, 'type_counts': {}, 'relation_total': 0}
    return _read(read_entities, tenant_id, project_id, source_ids, limit)


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
