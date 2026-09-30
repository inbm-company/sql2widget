from contextlib import contextmanager
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app import db, graph_ingestion as ingestion, graph_source_routes as routes
from app.auth import get_current_user
from app.main import app
from app.repositories import graph_sources as repo


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
                yield client, user
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            conn.rollback()


def test_registration_idempotency_scope_permissions_and_empty_failure(source_api):
    client, user = source_api
    # Canonical paths avoid duplicate records for a host path and relative path.
    first = client.post('/api/graph-sources', json={'name': '문서', 'path': '/vault'}).json()
    repeated = client.post('/api/graph-sources', json={'name': '문서', 'path': '.'}).json()
    assert first['id'] == repeated['id']
    assert first['status'] == 'registered'
    response = client.post(f"/api/graph-sources/{first['id']}/ingest")
    assert response.status_code == 400
    assert '적재할 문서가 없습니다' in response.json()['detail']
    assert repo.get_source(first['id'], user['tenant_id'])['status'] == 'failed'
    assert repo.get_source(first['id'], 'another-tenant') is None
    assert client.post('/api/graph-sources/missing/ingest').status_code == 404
    user['role'] = 'viewer'
    assert client.get('/api/graph-sources').status_code == 403
    assert client.post('/api/graph-sources', json={'name': '문서', 'path': '.'}).status_code == 403
    assert client.post(f"/api/graph-sources/{first['id']}/ingest").status_code == 403


def test_real_neo4j_reimport_is_idempotent_and_atomic(documents):
    (documents / 'one.md').write_text('# 첫 문서\n[[two]]\n' + '본문' * 3000, encoding='utf-8')
    (documents / 'two.md').write_text('# 두 번째', encoding='utf-8')
    docs, _ = ingestion.read_documents(documents)
    source = {'id': f'test_{uuid4().hex}', 'tenant_id': 'test-tenant', 'name': '테스트', 'path': '/vault'}
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
