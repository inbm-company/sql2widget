from contextlib import contextmanager
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app import db, graph_chat, graph_extraction as extraction, graph_schema, graph_service, graph_ingestion as ingestion, graph_source_routes as routes, project_graph
from app.auth import get_current_user
from app.main import app
from app.repositories import graph_sources as repo, projects


def test_upload_paths_are_normalized_filtered_and_confined():
    kept, excluded = ingestion.filter_upload([
        {'path': 'vault\\note.md', 'text': 'a'},
        {'path': '/abs/doc.txt', 'text': 'b'},
        {'path': './x/../y.md'.replace('x/../', ''), 'text': 'c'},
        {'path': 'vault/.obsidian/config.md', 'text': 'hidden'},
        {'path': '.git/readme.md', 'text': 'hidden'},
        {'path': 'vault/image.png', 'text': 'binary'},
    ])
    assert kept == {'vault/note.md': 'a', 'abs/doc.txt': 'b', 'y.md': 'c'}
    assert excluded == 3
    for path in ('../outside.md', 'a/../../b.md', '', '   ', 'a\x00.md'):
        with pytest.raises(ingestion.GraphSourceError):
            ingestion.clean_upload_path(path)


def test_links_chunks_and_empty_documents():
    files = {
        'one.md': '# 첫 문서\n[[two|별칭]] [[missing]]\n[두 번째](two.md#heading)\n'
                  '```md\n[[code-example]]\n```\n`[[inline-code]]`\n' + '본문' * 3000,
        'two.md': '# 두 번째\n[[one]]',
        'blank.txt': '',
    }
    docs, counts = ingestion.build_documents(files)
    assert counts['document_count'] == 2
    assert counts['link_count'] == 2
    assert counts['skipped_count'] == 1
    assert counts['unresolved_link_count'] == 1
    assert docs[0]['targets'] == ['two.md']
    assert docs[1]['targets'] == ['one.md']
    assert len(docs[0]['chunks']) > 1
    for chunk in docs[0]['chunks']:
        assert chunk['text'] == docs[0]['text'][chunk['start']:chunk['end']]
    assert all(len(chunk['text']) <= ingestion.CHUNK_SIZE for chunk in docs[0]['chunks'])


def test_chunks_overlap_cover_the_text_and_cut_at_paragraphs():
    paragraphs = '\n\n'.join(f'문단{i} ' + '가' * 900 for i in range(12))
    chunks = ingestion.chunks_for(paragraphs)
    assert len(chunks) > 1
    assert all(len(c['text']) <= ingestion.CHUNK_SIZE for c in chunks)
    assert all(c['text'] == paragraphs[c['start']:c['end']] for c in chunks)
    assert chunks[0]['start'] == 0 and chunks[-1]['end'] == len(paragraphs)
    for before, after in zip(chunks, chunks[1:]):
        assert 0 <= before['end'] - after['start'] <= ingestion.CHUNK_OVERLAP
        assert before['text'].endswith('\n\n')
        assert after['start'] == 0 or paragraphs[after['start'] - 1] == '\n'


def test_headings_are_metadata_only_and_ignored_in_code_and_plain_text():
    body = '| 컬럼 | 타입 |\n' + '| `col` | int |\n' * 400
    text = '# 제목\n## 1. orders\n' + body + '```bash\n# 주석은 제목이 아님\n```\n## 2. products\n' + body
    chunks = ingestion.chunks_for(text, markdown=True)
    assert chunks[0]['heading'] == '제목'
    assert any(c['heading'] == '2. products' for c in chunks)
    assert all(c['heading'] != '주석은 제목이 아님' for c in chunks)
    assert chunks[0]['start'] == 0 and len(chunks) == len(ingestion.chunks_for(text))
    plain = ingestion.chunks_for('# 제목 아님\n' + '나' * 100)
    assert len(plain) == 1 and plain[0]['heading'] is None


def test_ambiguous_links_do_not_invent_relationships():
    docs, counts = ingestion.build_documents({
        'a/same.md': '문서', 'b/same.md': '문서', 'start.md': '[[same]] [[a/same]]',
    })
    assert counts['unresolved_link_count'] == 1
    assert next(doc for doc in docs if doc['path'] == 'start.md')['targets'] == ['a/same.md']


def test_relative_links_stay_inside_the_upload():
    docs, counts = ingestion.build_documents({
        'notes/a.md': '[b](../top.md) [escape](../../outside.md) [abs](/etc/passwd.md)',
        'top.md': '# 최상위',
    })
    assert next(doc for doc in docs if doc['path'] == 'notes/a.md')['targets'] == ['top.md']
    assert counts['unresolved_link_count'] == 2


def test_empty_and_oversized_are_errors(monkeypatch):
    with pytest.raises(ingestion.GraphSourceError, match='적재할 문서가 없습니다'):
        ingestion.build_documents({})
    with pytest.raises(ingestion.GraphSourceError, match='적재할 문서가 없습니다'):
        ingestion.build_documents({'blank.md': '  \n'})
    with pytest.raises(ingestion.GraphSourceError, match='텍스트 파일이 아닙니다'):
        ingestion.build_documents({'bin.txt': 'a\x00b'})
    with pytest.raises(ingestion.GraphSourceError, match='UTF-8'):
        ingestion.build_documents({'bad.md': 'x\ud800'})
    monkeypatch.setattr(ingestion, 'MAX_FILE_BYTES', 10)
    with pytest.raises(ingestion.GraphSourceError, match='문서당 최대'):
        ingestion.build_documents({'note.md': 'x' * 11})


@pytest.fixture
def source_api(monkeypatch):
    original = db.get_conn
    with original() as conn:
        @contextmanager
        def transaction():
            yield conn

        monkeypatch.setattr(db, 'get_conn', transaction)
        monkeypatch.setattr(graph_service, 'get_conn', transaction)
        monkeypatch.setattr(repo, 'get_conn', transaction)
        user = {'id': 'user_admin', 'tenant_id': 'tenant_demo', 'role': 'admin'}
        app.dependency_overrides[get_current_user] = lambda: user
        try:
            with TestClient(app) as client:
                project = projects.create_project(user['tenant_id'], user['id'], '테스트 프로젝트')
                other = projects.create_project(user['tenant_id'], user['id'], '다른 프로젝트')
                yield client, user, project['id'], other['id']
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            conn.rollback()


def upload(*items):
    return [{'path': path, 'text': text} for path, text in items]


def test_upload_replace_ingest_scope_permissions_and_failure(source_api, monkeypatch):
    client, user, project, other = source_api
    base = f"/api/projects/{project}/graph-sources"
    created = client.post(base, json={'name': '문서', 'files': upload(
        ('vault/one.md', '# 하나\n[[two]]'), ('vault/two.md', '# 둘'),
        ('vault/.obsidian/x.md', 'hidden'), ('vault/pic.png', 'x'))})
    assert created.status_code == 200
    source = created.json()
    assert source['status'] == 'registered' and source['file_count'] == 2 and source['excluded_count'] == 2
    assert repo.get_files(source['id']) == {'vault/one.md': '# 하나\n[[two]]', 'vault/two.md': '# 둘'}
    # Same names are allowed: every upload is its own source.
    assert client.post(base, json={'name': '문서', 'files': upload(('a.md', 'x'))}).status_code == 200
    # Ingest reads the stored files and records the outcome.
    seen, real_ingest = {}, ingestion.ingest
    monkeypatch.setattr(ingestion, 'ingest', lambda src, files: seen.update(files=files) or
                        {'document_count': 2, 'chunk_count': 2, 'link_count': 1,
                         'skipped_count': 0, 'unresolved_link_count': 0})
    done = client.post(f"{base}/{source['id']}/ingest")
    assert done.status_code == 200 and done.json()['status'] == 'completed'
    assert set(seen['files']) == {'vault/one.md', 'vault/two.md'}
    # Replacing files resets the status so the new content is ingested again.
    replaced = client.put(f"{base}/{source['id']}/files", json={'files': upload(('new.md', '# 새 문서'))})
    assert replaced.status_code == 200
    assert replaced.json()['status'] == 'registered' and replaced.json()['file_count'] == 1
    assert repo.get_files(source['id']) == {'new.md': '# 새 문서'}
    # Invalid uploads fail before anything is stored.
    for body in ({'name': 'x', 'files': upload(('../escape.md', 'x'))},
                 {'name': 'x', 'files': upload(('pic.png', 'x'))},
                 {'name': 'x', 'files': upload(('blank.md', ' '))},
                 {'name': '  ', 'files': upload(('a.md', 'x'))}):
        assert client.post(base, json=body).status_code == 400
    assert client.post(base, json={'name': 'x', 'files': []}).status_code == 422
    assert len(client.get(base).json()['sources']) == 2
    # Real failure is surfaced, not hidden.
    monkeypatch.setattr(ingestion, 'ingest', real_ingest)
    db.execute('DELETE FROM graph_source_files WHERE source_id = %s', (source['id'],))
    failed = client.post(f"{base}/{source['id']}/ingest")
    assert failed.status_code == 400 and '적재할 문서가 없습니다' in failed.json()['detail']
    assert repo.get_source(source['id'], user['tenant_id'], project)['status'] == 'failed'
    assert repo.get_source(source['id'], 'another-tenant', project) is None
    assert client.post(f"/api/projects/{other}/graph-sources/{source['id']}/ingest").status_code == 404
    assert client.put(f"/api/projects/{other}/graph-sources/{source['id']}/files",
                      json={'files': upload(('a.md', 'x'))}).status_code == 404
    assert client.post(base + '/missing/ingest').status_code == 404
    user['role'] = 'viewer'
    assert client.get(base).status_code == 403
    assert client.post(base, json={'name': 'x', 'files': upload(('a.md', 'x'))}).status_code == 403
    assert client.put(f"{base}/{source['id']}/files", json={'files': upload(('a.md', 'x'))}).status_code == 403
    assert client.post(f"{base}/{source['id']}/ingest").status_code == 403


def test_real_neo4j_reimport_is_idempotent_and_atomic():
    files = {'one.md': '# 첫 문서\n[[two]]\n' + '본문' * 3000, 'two.md': '# 두 번째'}
    docs, _ = ingestion.build_documents(files)
    source = {'id': f'test_{uuid4().hex}', 'tenant_id': 'test-tenant', 'project_id': 'test-project', 'name': '테스트', 'path': '/vault'}
    driver = ingestion.graph_driver()
    with driver.session(database='neo4j') as session:
        tx = session.begin_transaction()
        try:
            ingestion.write_graph(tx, source, docs)
            ingestion.write_graph(tx, source, docs)
            record = tx.run('MATCH (d:GraphDocument {source_id: $id}) RETURN count(d) AS n', id=source['id']).single()
            assert record['n'] == 2
            assert tx.run('MATCH (d:GraphDocument {source_id: $id})-[r:LINKS_TO]->() '
                          'WHERE r.active RETURN count(r) AS n', id=source['id']).single()['n'] == 1
            updated, _ = ingestion.build_documents({**files, 'one.md': '짧은 새 본문'})
            ingestion.write_graph(tx, source, updated)
            assert tx.run('MATCH (c:GraphChunk {source_id: $id}) WHERE c.active '
                          'RETURN count(c) AS n', id=source['id']).single()['n'] == 2
            assert tx.run('MATCH (d:GraphDocument {source_id: $id})-[r:LINKS_TO]->() '
                          'WHERE r.active RETURN count(r) AS n', id=source['id']).single()['n'] == 0
            # A second source never shares document IDs or relations.
            other = {**source, 'id': source['id'] + '_other', 'tenant_id': 'another-tenant'}
            ingestion.write_graph(tx, other, updated)
            assert tx.run('MATCH (d:GraphDocument {source_id: $id}) RETURN count(d) AS n', id=source['id']).single()['n'] == 2
        finally:
            tx.rollback()
    with driver.session(database='neo4j') as session:
        assert session.run('MATCH (s:GraphSource {id: $id}) RETURN count(s) AS n', id=source['id']).single()['n'] == 0


def test_project_and_owner_isolation(source_api):
    client, user, project, other = source_api
    base = f'/api/projects/{project}'
    first = client.post(base + '/graph-sources', json={'name': '첫 소스', 'files': upload(('a.md', 'x'))}).json()
    second = client.post(f'/api/projects/{other}/graph-sources', json={'name': '다른 소스', 'files': upload(('a.md', 'x'))}).json()
    assert first['id'] != second['id']
    assert [s['id'] for s in client.get(base + '/graph-sources').json()['sources']] == [first['id']]
    assert client.post(f"/api/projects/{other}/graph-sources/{first['id']}/ingest").status_code == 404
    assert client.get('/api/graph-sources').status_code == 404
    assert client.get(base + '/graph?limit=501').status_code == 422
    assert client.get(base + '/graph/documents/missing').status_code == 404
    user['id'] = 'another-owner'
    for path in ('/graph', '/graph-sources', '/graph/documents/missing'):
        assert client.get(base + path).status_code == 404
    assert client.post(base + '/graph-sources', json={'name': 'x', 'files': upload(('a.md', 'x'))}).status_code == 404
    user['id'] = 'user_admin'
    user['tenant_id'] = 'another-tenant'
    assert client.get(base + '/graph').status_code == 404


def test_empty_graph_viewer_and_connection_error(source_api, monkeypatch):
    client, user, project, _ = source_api
    user['role'] = 'viewer'
    response = client.get(f'/api/projects/{project}/graph')
    assert response.status_code == 200
    assert response.json()['nodes'] == []
    assert response.json()['totals']['source_count'] == 0
    user['role'] = 'admin'
    client.post(f'/api/projects/{project}/graph-sources', json={'name': 'x', 'files': upload(('a.md', 'x'))})
    def unavailable(*args):
        raise ingestion.GraphSourceError('Neo4j unavailable')
    monkeypatch.setattr(project_graph, 'project_graph', unavailable)
    assert client.get(f'/api/projects/{project}/graph').status_code == 502


def test_real_graph_scope_and_content_limits():
    text = '# 첫 문서\n[[two]]\n' + '본문' * 3000
    files = {'one.md': text, 'two.md': '# 두 번째'}
    docs, _ = ingestion.build_documents(files)
    source = {'id': f'test_{uuid4().hex}', 'tenant_id': 'test-tenant', 'project_id': 'project-a', 'name': '문서', 'path': '/vault'}
    other = {**source, 'id': source['id'] + '_other', 'project_id': 'project-b'}
    driver = ingestion.graph_driver()
    with driver.session(database='neo4j') as session:
        tx = session.begin_transaction()
        try:
            ingestion.write_graph(tx, source, docs)
            ingestion.write_graph(tx, other, docs)
            ids = [source['id'], other['id']]
            graph = project_graph.read_graph(tx, 'test-tenant', 'project-a', ids, 200)
            assert len(graph['nodes']) == 2
            assert graph['totals']['link_count'] == 1
            assert all(node['source_id'] == source['id'] for node in graph['nodes'])
            doc_id = ingestion.document_id(source['id'], 'one.md')
            assert project_graph.read_document(tx, 'test-tenant', 'project-a', ids, doc_id)['content'] == text
            assert project_graph.read_document(tx, 'test-tenant', 'project-b', ids, doc_id) is None
            assert project_graph.read_document(tx, 'another-tenant', 'project-a', ids, doc_id) is None
            assert project_graph.read_document(tx, 'test-tenant', 'project-a', [other['id']], doc_id) is None
            limited = project_graph.read_graph(tx, 'test-tenant', 'project-a', ids, 1)
            assert len(limited['nodes']) == 1 and limited['truncated']
            assert limited['links'] == []
            # Reimport excludes removed records and their links from the active view.
            updated, _ = ingestion.build_documents({'one.md': '새 본문'})
            ingestion.write_graph(tx, {**source, 'project_id': 'project-a'}, updated)
            assert project_graph.read_graph(tx, 'test-tenant', 'project-a', ids, 200)['totals']['document_count'] == 1
            assert project_graph.read_document(tx, 'test-tenant', 'project-a', ids, doc_id)['content'] == '새 본문'
            long_text = '본문' * 60000
            long_docs, _ = ingestion.build_documents({'one.md': long_text})
            ingestion.write_graph(tx, {**source, 'project_id': 'project-a'}, long_docs)
            detail = project_graph.read_document(tx, 'test-tenant', 'project-a', ids, doc_id)
            assert detail['content'] == long_text[:project_graph.MAX_CONTENT_CHARS]
            assert detail['content_truncated'] is True
        finally:
            tx.rollback()


GOOD_SCHEMA = {
    'entity_types': [{'name': 'Table', 'description': '테이블', 'examples': ['orders'], 'properties': ['row_count']},
                     {'name': 'Region', 'description': '권역', 'examples': ['Eastern'], 'properties': []}],
    'relation_types': [{'name': 'REFERENCES', 'from': 'Table', 'to': 'Table', 'description': 'FK'}],
    'questions': ['Column도 노드로 만들까요?'],
}


def test_schema_validation_keeps_types_closed():
    assert graph_schema.validate_schema(GOOD_SCHEMA)['entity_types'][0]['name'] == 'Table'
    bad = [
        {'entity_types': []},
        {'entity_types': [{'name': 'table'}]},
        {'entity_types': [{'name': 'GraphChunk'}]},
        {'entity_types': [{'name': 'A`) DETACH DELETE (n'}]},
        {'entity_types': [{'name': 'A'}, {'name': 'A'}]},
        {'entity_types': [{'name': 'A', 'properties': ['Bad Name']}]},
        {'entity_types': [{'name': 'A'}], 'relation_types': [{'name': 'USES', 'from': 'A', 'to': 'Missing'}]},
        {'entity_types': [{'name': 'A'}], 'relation_types': [{'name': 'LINKS_TO', 'from': 'A', 'to': 'A'}]},
        {'entity_types': [{'name': 'A'}], 'relation_types': [{'name': 'uses', 'from': 'A', 'to': 'A'}]},
    ]
    for raw in bad:
        with pytest.raises(ingestion.GraphSourceError):
            graph_schema.validate_schema(raw)


def test_types_without_documented_examples_are_dropped_and_reported():
    schema = graph_schema.validate_schema({
        'entity_types': [{'name': 'Table', 'examples': ['orders', 'nope']}, {'name': 'Order', 'examples': ['주문들']}],
        'relation_types': [{'name': 'ABOUT', 'from': 'Table', 'to': 'Order'}]})
    kept = graph_schema.keep_supported_types(schema, {'a.md': '### 5.1 `orders` — 주문'})
    assert [e['name'] for e in kept['entity_types']] == ['Table']
    assert kept['entity_types'][0]['examples'] == ['orders'] and kept['relation_types'] == []
    assert 'Order' in kept['questions'][0]
    with pytest.raises(ingestion.GraphSourceError):
        graph_schema.keep_supported_types(schema, {'a.md': '관계없는 문서'})


def test_schema_proposal_edit_and_approval_flow(source_api, monkeypatch):
    client, user, project, other = source_api
    base = f"/api/projects/{project}/graph-sources"
    source = client.post(base, json={'name': '스키마 문서', 'files': upload(('db.md', '# DB\n## orders\nEastern 권역 컬럼'))}).json()
    assert source['schema_status'] == 'none' and source['schema_draft'] is None
    url = f"{base}/{source['id']}/schema"
    assert client.post(f'{url}/approve').status_code == 400

    calls = []

    def fake_llm(system_hint, user_content, **kwargs):
        calls.append((user_content, kwargs))
        return {'provider': 'x', 'result': GOOD_SCHEMA, 'model': 'm'}

    monkeypatch.setattr(graph_schema, 'json_with_llm', fake_llm)
    headers = {'X-LLM-Provider': 'openai', 'X-LLM-API-Key': 'k', 'X-LLM-Model': 'm'}
    proposed = client.post(f'{url}/propose', json={}, headers=headers)
    assert proposed.status_code == 200
    assert proposed.json()['schema_status'] == 'proposed'
    assert proposed.json()['schema_draft']['questions'] == ['Column도 노드로 만들까요?']
    assert calls[0][0]['current_schema'] is None
    assert calls[0][0]['documents'][0]['headings'] == ['DB', 'orders']
    assert calls[0][1]['runtime_provider'] == 'openai' and calls[0][1]['runtime_model'] == 'm'

    client.post(f'{url}/propose', json={'instruction': 'Column도 노드로'}, headers=headers)
    assert calls[1][0]['current_schema']['entity_types'][0]['name'] == 'Table'
    assert calls[1][0]['instruction'] == 'Column도 노드로'

    assert client.put(url, json={'schema': {'entity_types': [{'name': 'bad name'}]}}).status_code == 400
    edited = {**GOOD_SCHEMA, 'questions': []}
    approved = client.post(f'{url}/approve')
    assert approved.status_code == 200 and approved.json()['schema_status'] == 'approved'
    assert client.put(url, json={'schema': edited}).json()['schema_status'] == 'proposed'
    assert client.post(f"/api/projects/{other}/graph-sources/{source['id']}/schema/approve").status_code == 404


def test_schema_proposal_failure_is_reported_not_guessed(source_api, monkeypatch):
    client, user, project, other = source_api
    base = f"/api/projects/{project}/graph-sources"
    source = client.post(base, json={'name': '문서', 'files': upload(('a.md', '# a'))}).json()
    monkeypatch.setattr(graph_schema, 'json_with_llm',
                        lambda *a, **k: {'provider': 'x', 'result': None, 'error': 'API key missing'})
    response = client.post(f"{base}/{source['id']}/schema/propose", json={})
    assert response.status_code == 502 and 'API key missing' in response.json()['detail']
    stored = repo.get_source(source['id'], user['tenant_id'], project)
    assert stored['schema_status'] == 'none' and stored['schema_draft'] is None
    monkeypatch.setattr(graph_schema, 'json_with_llm',
                        lambda *a, **k: {'provider': 'x', 'result': {'entity_types': [{'name': 'bad name'}]}})
    assert client.post(f"{base}/{source['id']}/schema/propose", json={}).status_code == 502


NW_CHUNK = ('### 5.1 `orders` — 주문\n| `customer_id` | varchar(5) | FK → `customers` | 주문 고객 |\n'
            '### 5.6 `customers` — 고객\n')


def test_extraction_keeps_only_schema_types_with_evidence_in_the_chunk():
    schema = graph_schema.validate_schema(GOOD_SCHEMA)
    raw = {
        'entities': [
            {'type': 'Table', 'name': 'orders', 'evidence': '### 5.1 orders — 주문', 'properties': {'row_count': 3830, 'bad': 1}},
            {'type': 'Table', 'name': 'invented', 'evidence': '### 5.1 orders'},
            {'type': 'Person', 'name': 'orders', 'evidence': '### 5.1 orders'},
            {'type': 'Table', 'name': 'customers', 'evidence': '꾸며낸 문장'},
            {'type': 'Table', 'name': 'customers', 'evidence': '### 5.6 customers — 고객'},
        ],
        'relations': [
            {'type': 'REFERENCES', 'from': 'orders', 'to': 'customers', 'evidence': 'customer_id | varchar(5) | FK → customers'},
            {'type': 'REFERENCES', 'from': 'orders', 'to': 'ghost', 'evidence': 'customer_id'},
            {'type': 'UNKNOWN', 'from': 'orders', 'to': 'customers', 'evidence': 'customer_id'},
            {'type': 'REFERENCES', 'from': 'orders', 'to': 'customers', 'evidence': '지어낸 근거'},
        ],
    }
    entities, relations = extraction.validate_extraction(raw, schema, NW_CHUNK)
    assert [e['name'] for e in entities] == ['orders', 'customers']
    assert entities[0]['properties'] == {'row_count': 3830}
    assert [(r['from'], r['to'], r['from_type']) for r in relations] == [('orders', 'customers', 'Table')]
    with pytest.raises(ingestion.GraphSourceError):
        extraction.validate_extraction([], schema, NW_CHUNK)


def test_merge_results_dedupes_and_adds_relation_endpoints():
    chunks = [{'id': 'c1'}, {'id': 'c2'}]
    rel = {'type': 'REFERENCES', 'from_type': 'Table', 'from': 'Orders', 'to_type': 'Table', 'to': 'customers',
           'evidence': 'FK'}
    ent = {'type': 'Table', 'name': 'orders', 'properties': {'row_count': 1}, 'evidence': 'e'}
    entities, relations = extraction.merge_results('src', [(chunks[0], [ent], [rel]), (chunks[1], [ent], [rel])])
    assert sorted(e['name'] for e in entities.values()) == ['customers', 'orders']
    assert len(entities) == 2 and len(relations) == 1
    assert set(next(e for e in entities.values() if e['name'].lower() == 'orders')['chunks']) == {'c1', 'c2'}


class FakeSession:
    def __init__(self, writes):
        self.writes = writes

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute_write(self, fn, *args):
        self.writes.append(args)


class FakeDriver:
    def __init__(self):
        self.writes = []

    def execute_query(self, *args, **kwargs):
        return None

    def session(self, **kwargs):
        return FakeSession(self.writes)


def ready_source(client, base, monkeypatch):
    """Create an ingested source with an approved schema (the Neo4j write is replaced by a fake)."""
    source = client.post(base, json={'name': '스키마 문서', 'files': upload(('nw.md', NW_CHUNK))}).json()
    monkeypatch.setattr(ingestion, 'ingest', lambda s, files: {
        'document_count': 1, 'chunk_count': 1, 'link_count': 0, 'skipped_count': 0, 'unresolved_link_count': 0})
    assert client.post(f"{base}/{source['id']}/ingest").status_code == 200
    return source


def test_extract_endpoint_requires_approved_schema_and_ingestion_and_blocks_concurrency(source_api, monkeypatch):
    client, user, project, other = source_api
    base = f"/api/projects/{project}/graph-sources"
    source = client.post(base, json={'name': '문서', 'files': upload(('nw.md', NW_CHUNK))}).json()
    url = f"{base}/{source['id']}"
    started = []
    monkeypatch.setattr(extraction, 'start_job', lambda *a, **k: started.append((a, k)))
    assert client.post(f'{url}/extract').status_code == 400
    client.put(f'{url}/schema', json={'schema': GOOD_SCHEMA})
    client.post(f'{url}/schema/approve')
    assert client.post(f'{url}/extract').status_code == 400  # approved but not ingested yet
    monkeypatch.setattr(ingestion, 'ingest', lambda s, files: {
        'document_count': 1, 'chunk_count': 1, 'link_count': 0, 'skipped_count': 0, 'unresolved_link_count': 0})
    assert client.post(f'{url}/ingest').status_code == 200
    first = client.post(f'{url}/extract', headers={'X-LLM-Provider': 'openai', 'X-LLM-API-Key': 'k'})
    assert first.status_code == 200 and first.json()['extract_status'] == 'running'
    assert first.json()['extract_progress'] == {'done': 0, 'total': 1, 'failed': 0}
    assert started[0][1]['llm_settings']['api_key'] == 'k'
    assert client.post(f'{url}/extract').status_code == 409
    assert client.post(f'{url}/ingest').status_code == 409
    assert client.put(f'{url}/files', json={'files': upload(('a.md', 'x'))}).status_code == 409
    assert client.post(f'{url}/extract/cancel').status_code == 409  # no job registered in this process


def test_run_job_publishes_entities_and_reports_failures(source_api, monkeypatch):
    client, user, project, other = source_api
    base = f"/api/projects/{project}/graph-sources"
    source = ready_source(client, base, monkeypatch)
    client.put(f"{base}/{source['id']}/schema", json={'schema': GOOD_SCHEMA})
    client.post(f"{base}/{source['id']}/schema/approve")
    source = repo.get_source(source['id'], user['tenant_id'], project)
    plan = extraction.chunk_plan(source['id'], repo.get_files(source['id']))
    assert plan[0]['id'].endswith(':0')
    schema = graph_schema.validate_schema(GOOD_SCHEMA)
    driver = FakeDriver()
    monkeypatch.setattr(extraction, 'graph_driver', lambda: driver)

    def run(llm):
        monkeypatch.setattr(extraction, 'json_with_llm', llm)
        repo.start_extract(source['id'], user['tenant_id'], project, len(plan))
        extraction._cancel_events[source['id']] = extraction.threading.Event()
        extraction.run_job(source, schema, plan, user_id=user['id'], llm_settings={})
        return repo.get_source(source['id'], user['tenant_id'], project)

    good = {'entities': [{'type': 'Table', 'name': 'orders', 'evidence': '### 5.1 orders'}],
            'relations': [{'type': 'REFERENCES', 'from': 'orders', 'to': 'customers',
                           'evidence': 'FK → customers'}]}
    done = run(lambda *a, **k: {'result': good})
    assert done['extract_status'] == 'completed' and done['entity_count'] == 2 and done['relation_count'] == 1
    assert done['last_extracted_at'] is not None and len(driver.writes) == 1

    failed = run(lambda *a, **k: {'result': None, 'error': 'API key missing'})
    assert failed['extract_status'] == 'failed' and 'API key missing' in failed['extract_error']
    assert failed['entity_count'] == 2 and len(driver.writes) == 1  # earlier result untouched


def test_interrupted_extractions_are_failed_at_startup(source_api):
    client, user, project, other = source_api
    base = f"/api/projects/{project}/graph-sources"
    source = client.post(base, json={'name': '문서', 'files': upload(('a.md', '# a'))}).json()
    repo.start_extract(source['id'], user['tenant_id'], project, 1)
    assert repo.fail_interrupted_extractions() >= 1
    stored = repo.get_source(source['id'], user['tenant_id'], project)
    assert stored['extract_status'] == 'failed' and '재시작' in stored['extract_error']


def chat_turn(user, project, message, action=None, source_id=None):
    return graph_chat.handle(message, user=user, project_id=project, llm_settings={'provider': 'x'},
                             action=action, meta={})


def test_chat_flow_proposes_revises_approves_extracts_and_cancels(source_api, monkeypatch):
    client, user, project, other = source_api
    base = f"/api/projects/{project}/graph-sources"
    assert '올린 문서가 없어요' in chat_turn(user, project, '그래프 만들어줘')[0]
    source = client.post(base, json={'name': '스키마 문서', 'files': upload(('nw.md', NW_CHUNK))}).json()
    calls = []
    monkeypatch.setattr(graph_schema, 'json_with_llm', lambda hint, content, **kw: (
        calls.append(content) or {'provider': 'x', 'result': {
            **GOOD_SCHEMA, 'entity_types': [{**GOOD_SCHEMA['entity_types'][0], 'examples': ['orders']},
                                             {**GOOD_SCHEMA['entity_types'][1], 'examples': ['customers']}]}}))
    monkeypatch.setattr(ingestion, 'ingest', lambda s, files: {
        'document_count': 1, 'chunk_count': 1, 'link_count': 0, 'skipped_count': 0, 'unresolved_link_count': 0})
    started = []
    monkeypatch.setattr(extraction, 'start_job', lambda *a, **k: started.append(a))

    summary, artifact, meta = chat_turn(user, project, '문서를 그래프로 만들어줘')
    assert artifact['type'] == 'graph_flow' and artifact['graph']['schema_status'] == 'proposed'
    assert [c['action']['type'] for c in artifact['choices']] == ['approve', 'regenerate']
    assert meta['route'] == 'graph_build' and calls[0]['instruction'] == ''

    chat_turn(user, project, 'Column도 노드로 해줘')  # free text while proposed revises the draft
    assert calls[1]['instruction'] == 'Column도 노드로 해줘' and calls[1]['current_schema'] is not None

    summary, artifact, _ = chat_turn(user, project, '승인', {'type': 'approve', 'source_id': source['id']})
    assert '추출을 시작' in summary and started  # ingested automatically, then extraction started
    stored = repo.get_source(source['id'], user['tenant_id'], project)
    assert stored['schema_status'] == 'approved' and stored['status'] == 'completed'
    assert stored['extract_status'] == 'running'
    assert artifact['choices'][0]['action']['type'] == 'cancel'

    assert '추출하는 중' in chat_turn(user, project, '그래프 상태는?')[0]
    assert '진행하지 못했어요' in chat_turn(user, project, '다시', {'type': 'extract', 'source_id': source['id']})[0]
    assert '진행하지 못했어요' in chat_turn(user, project, '취소', {'type': 'cancel', 'source_id': source['id']})[0]
    # no job thread is registered in this process (start_job is faked), so cancel is reported, not hidden


def test_chat_flow_is_admin_only_and_asks_which_source(source_api, monkeypatch):
    client, user, project, other = source_api
    assert '관리자만' in chat_turn({**user, 'role': 'user'}, project, '그래프')[0]
    base = f"/api/projects/{project}/graph-sources"
    for name in ('하나', '둘'):
        client.post(base, json={'name': name, 'files': upload(('a.md', '# a'))})
    summary, artifact, _ = chat_turn(user, project, '그래프 만들어줘')
    assert '어느 문서 소스' in summary
    assert [c['action']['type'] for c in artifact['choices']] == ['select', 'select']


def test_router_knows_graph_build_and_pending_flow(monkeypatch):
    from app import intent_router as router
    assert 'graph_build' in router.ANSWER_ROUTES and 'graph_build' in router.JEV_CRITERIA
    decision = router.decide_route('Column도 노드로', tables=set(),
                                   forced_route='graph_build', llm_context={}, pending_graph_flow=True)
    assert decision['route'] == 'graph_build' and decision['clarify'] is False
    seen = {}
    monkeypatch.setattr(router.config, 'TYPESAFE_API_KEY', 'k')
    monkeypatch.setattr(router, 'route_with_jev', lambda state: seen.update(state) or {
        'route': 'graph_build', 'confidence': 0.9, 'probabilities': {}, 'source': 'jev'})
    router.decide_route('그렇게 해줘', tables=set(), forced_route=None,
                        llm_context={}, pending_graph_flow=True)
    assert seen['pending_graph_flow'] is True
