from contextlib import contextmanager
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app import db, graph_ingestion as ingestion, graph_source_routes as routes, project_graph
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
    chunks = docs[0]['chunks']
    assert chunks[0]['end'] - chunks[1]['start'] == ingestion.CHUNK_OVERLAP


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
        monkeypatch.setattr(routes, 'get_conn', transaction)
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
