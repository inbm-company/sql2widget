from contextlib import contextmanager
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app import db, graph_ingestion as ingestion, graph_source_routes as routes, project_graph
from app.auth import get_current_user
from app.main import app
from app.repositories import graph_sources as repo, projects


@pytest.fixture
def documents(tmp_path, monkeypatch):
    monkeypatch.setattr(ingestion, 'SOURCE_ROOT', tmp_path)
    monkeypatch.setattr(ingestion, 'HOST_ROOT', '/vault')
    return tmp_path


def test_paths_reject_escape_hidden_and_symlink(documents, tmp_path_factory):
    (documents / 'note.md').write_text('# 문서', encoding='utf-8')
    expected = documents / 'note.md'
    assert ingestion.resolve_source_path('/vault/note.md')[0] == expected
    assert ingestion.resolve_source_path('note.md')[0] == expected
    assert ingestion.resolve_source_path(str(expected))[0] == expected
    outside = tmp_path_factory.mktemp('outside') / 'outside.md'
    outside.write_text('outside', encoding='utf-8')
    (documents / 'escape.md').symlink_to(outside)
    for path in ('/etc/passwd', '/vault/../outside', '/vault/.obsidian', '/vault/escape.md'):
        with pytest.raises(ingestion.GraphSourceError):
            ingestion.resolve_source_path(path)
    with pytest.raises(ingestion.GraphSourceError):
        ingestion.read_documents(documents)


def test_obsidian_links_chunks_and_excluded_files(documents):
    (documents / '.obsidian').mkdir()
    (documents / '.obsidian' / 'config.md').write_text('hidden', encoding='utf-8')
    (documents / 'image.png').write_bytes(b'image')
    (documents / 'blank.txt').write_text('', encoding='utf-8')
    (documents / 'one.md').write_text(
        '# 첫 문서\n[[two|별칭]] [[missing]]\n[두 번째](two.md#heading)\n'
        '```md\n[[code-example]]\n```\n`[[inline-code]]`\n' + '본문' * 3000,
        encoding='utf-8',
    )
    (documents / 'two.md').write_text('# 두 번째\n[[one]]', encoding='utf-8')
    docs, counts = ingestion.read_documents(documents)
    assert counts['document_count'] == 2
    assert counts['link_count'] == 2
    assert counts['skipped_count'] == 2
    assert counts['unresolved_link_count'] == 1
    assert docs[0]['targets'] == ['two.md']
    assert docs[1]['targets'] == ['one.md']
    assert len(docs[0]['chunks']) > 1
    for chunk in docs[0]['chunks']:
        assert chunk['text'] == docs[0]['text'][chunk['start']:chunk['end']]
    chunks = docs[0]['chunks']
    assert chunks[0]['end'] - chunks[1]['start'] == ingestion.CHUNK_OVERLAP


def test_ambiguous_links_do_not_invent_relationships(documents):
    for folder in ('a', 'b'):
        (documents / folder).mkdir()
        (documents / folder / 'same.md').write_text('문서', encoding='utf-8')
    (documents / 'start.md').write_text('[[same]] [[a/same]]', encoding='utf-8')
    docs, counts = ingestion.read_documents(documents)
    assert counts['unresolved_link_count'] == 1
    assert next(doc for doc in docs if doc['path'] == 'start.md')['targets'] == ['a/same.md']


def test_empty_invalid_utf8_and_oversized_are_errors(documents, monkeypatch):
    with pytest.raises(ingestion.GraphSourceError, match='적재할 문서가 없습니다'):
        ingestion.read_documents(documents)
    note = documents / 'note.md'
    note.write_bytes(b'\xff')
    with pytest.raises(ingestion.GraphSourceError, match='UTF-8'):
        ingestion.read_documents(documents)
    note.write_bytes(b'x' * 11)
    monkeypatch.setattr(ingestion, 'MAX_FILE_BYTES', 10)
    with pytest.raises(ingestion.GraphSourceError, match='문서당 최대'):
        ingestion.read_documents(documents)


@pytest.fixture
def source_api(documents, monkeypatch):
    original = db.get_conn
    with original() as conn:
        @contextmanager
        def transaction():
            yield conn

        monkeypatch.setattr(db, 'get_conn', transaction)
        monkeypatch.setattr(routes, 'get_conn', transaction)
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


def test_registration_idempotency_scope_permissions_and_empty_failure(source_api):
    client, user, project, other = source_api
    base = f"/api/projects/{project}/graph-sources"
    # Canonical paths avoid duplicate records for a host path and relative path.
    first = client.post(base, json={'name': '문서', 'path': '/vault'}).json()
    repeated = client.post(base, json={'name': '문서', 'path': '.'}).json()
    assert first['id'] == repeated['id']
    assert first['status'] == 'registered'
    response = client.post(f"{base}/{first['id']}/ingest")
    assert response.status_code == 400
    assert '적재할 문서가 없습니다' in response.json()['detail']
    assert repo.get_source(first['id'], user['tenant_id'], project)['status'] == 'failed'
    assert repo.get_source(first['id'], 'another-tenant', project) is None
    assert client.post(base + '/missing/ingest').status_code == 404
    user['role'] = 'viewer'
    assert client.get(base).status_code == 403
    assert client.post(base, json={'name': '문서', 'path': '.'}).status_code == 403
    assert client.post(f"{base}/{first['id']}/ingest").status_code == 403


def test_real_neo4j_reimport_is_idempotent_and_atomic(documents):
    (documents / 'one.md').write_text('# 첫 문서\n[[two]]\n' + '본문' * 3000, encoding='utf-8')
    (documents / 'two.md').write_text('# 두 번째', encoding='utf-8')
    docs, _ = ingestion.read_documents(documents)
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
            (documents / 'one.md').write_text('짧은 새 본문', encoding='utf-8')
            updated, _ = ingestion.read_documents(documents)
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
    first = client.post(base + '/graph-sources', json={'name': '첫 소스', 'path': '.'}).json()
    second = client.post(f'/api/projects/{other}/graph-sources', json={'name': '다른 소스', 'path': '.'}).json()
    assert first['id'] != second['id']
    assert [s['id'] for s in client.get(base + '/graph-sources').json()['sources']] == [first['id']]
    assert client.post(f"/api/projects/{other}/graph-sources/{first['id']}/ingest").status_code == 404
    assert client.get('/api/graph-sources').status_code == 404
    assert client.get(base + '/graph?limit=501').status_code == 422
    assert client.get(base + '/graph/documents/missing').status_code == 404
    user['id'] = 'another-owner'
    for path in ('/graph', '/graph-sources', '/graph/documents/missing'):
        assert client.get(base + path).status_code == 404
    assert client.post(base + '/graph-sources', json={'name': 'x', 'path': '.'}).status_code == 404
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
    client.post(f'/api/projects/{project}/graph-sources', json={'name': 'x', 'path': '.'})
    def unavailable(*args):
        raise ingestion.GraphSourceError('Neo4j unavailable')
    monkeypatch.setattr(project_graph, 'project_graph', unavailable)
    assert client.get(f'/api/projects/{project}/graph').status_code == 502


def test_unassigned_sources_require_creator_and_explicit_assignment(source_api, monkeypatch):
    client, user, project, other = source_api
    source_id = f'test_legacy_{uuid4().hex}'
    db.execute('INSERT INTO graph_sources (id, tenant_id, created_by, name, path) VALUES (%s, %s, %s, %s, %s)',
               (source_id, user['tenant_id'], user['id'], '기존 문서', '/vault'))
    calls = []
    monkeypatch.setattr(project_graph, 'assign_graph_project', lambda *args: calls.append(args))
    base = f'/api/projects/{project}/graph-sources'
    unassigned = client.get(base).json()['unassigned_sources']
    assert source_id in [s['id'] for s in unassigned]
    assert repo.get_source(source_id, user['tenant_id'], project) is None
    client.post(base, json={'name': '중복', 'path': '.'})
    assert client.post(f'{base}/{source_id}/assign').status_code == 409
    assert calls == []
    target = f'/api/projects/{other}/graph-sources'
    assigned = client.post(f'{target}/{source_id}/assign')
    assert assigned.status_code == 200
    assert assigned.json()['project_id'] == other
    assert calls == [(source_id, user['tenant_id'], other)]
    assert client.post(f'{target}/{source_id}/assign').status_code == 404
    assert source_id not in [s['id'] for s in client.get(base).json()['unassigned_sources']]
    db.execute('UPDATE graph_sources SET project_id = NULL, created_by = %s WHERE id = %s', ('user_viewer', source_id))
    assert source_id not in [s['id'] for s in client.get(target).json()['unassigned_sources']]
    assert client.post(f'{target}/{source_id}/assign').status_code == 404


def test_real_graph_scope_content_limits_and_legacy_assignment(documents):
    text = '# 첫 문서\n[[two]]\n' + '본문' * 3000
    (documents / 'one.md').write_text(text, encoding='utf-8')
    (documents / 'two.md').write_text('# 두 번째', encoding='utf-8')
    docs, _ = ingestion.read_documents(documents)
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
            # Simulate legacy records, then connect without replacing IDs or content.
            tx.run('MATCH (n) WHERE n.source_id = $source OR n.id = $source REMOVE n.project_id', source=source['id']).consume()
            tx.run('MATCH (d:GraphDocument {source_id: $source})-[r:LINKS_TO]->() REMOVE r.project_id, r.tenant_id', source=source['id']).consume()
            project_graph.tag_source_project(tx, source['id'], 'test-tenant', 'project-c')
            assert project_graph.read_graph(tx, 'test-tenant', 'project-a', ids, 200)['nodes'] == []
            moved = project_graph.read_graph(tx, 'test-tenant', 'project-c', ids, 200)
            assert len(moved['nodes']) == 2 and moved['totals']['link_count'] == 1
            assert project_graph.read_document(tx, 'test-tenant', 'project-c', ids, doc_id)['content'] == text
            # Reimport excludes removed records and their links from the active view.
            (documents / 'two.md').unlink()
            (documents / 'one.md').write_text('새 본문', encoding='utf-8')
            updated, _ = ingestion.read_documents(documents)
            ingestion.write_graph(tx, {**source, 'project_id': 'project-c'}, updated)
            assert project_graph.read_graph(tx, 'test-tenant', 'project-c', ids, 200)['totals']['document_count'] == 1
            assert project_graph.read_document(tx, 'test-tenant', 'project-c', ids, doc_id)['content'] == '새 본문'
            long_text = '본문' * 60000
            (documents / 'one.md').write_text(long_text, encoding='utf-8')
            long_docs, _ = ingestion.read_documents(documents)
            ingestion.write_graph(tx, {**source, 'project_id': 'project-c'}, long_docs)
            detail = project_graph.read_document(tx, 'test-tenant', 'project-c', ids, doc_id)
            assert detail['content'] == long_text[:project_graph.MAX_CONTENT_CHARS]
            assert detail['content_truncated'] is True
        finally:
            tx.rollback()
