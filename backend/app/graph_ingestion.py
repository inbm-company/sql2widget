"""Read local documents and preserve their text and explicit links in Neo4j."""

import hashlib
import os
import re
from collections import defaultdict
from functools import lru_cache
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError, ServiceUnavailable

SOURCE_ROOT = Path(os.getenv('GRAPH_RAG_SOURCE_ROOT', '/graph-rag-sources'))
HOST_ROOT = os.getenv('GRAPH_RAG_HOST_PATH', './graph-rag-sources').rstrip('/')
SUPPORTED_EXTENSIONS = {'.md', '.txt'}
MAX_FILES = 1000
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 20 * 1024 * 1024
CHUNK_SIZE = 4000
CHUNK_OVERLAP = 400


class GraphSourceError(ValueError):
    pass


def resolve_source_path(value: str) -> tuple[Path, str]:
    """Map a registered host path into the one read-only mounted source root."""
    value = value.strip()
    if not value or '\x00' in value:
        raise GraphSourceError('폴더 또는 파일 경로를 입력하세요.')
    candidate = PurePosixPath(value)
    host = PurePosixPath(HOST_ROOT)
    try:
        if candidate.is_absolute():
            if host.is_absolute() and candidate.is_relative_to(host):
                relative = candidate.relative_to(host)
            else:
                relative = candidate.relative_to(PurePosixPath(str(SOURCE_ROOT)))
        elif candidate.is_relative_to(host):
            relative = candidate.relative_to(host)
        else:
            relative = candidate
    except ValueError:
        raise GraphSourceError('공유된 문서 폴더 안의 경로만 등록할 수 있습니다.') from None
    root = SOURCE_ROOT.resolve()
    try:
        resolved = (root / str(relative)).resolve()
        normalized = resolved.relative_to(root)
    except (ValueError, OSError, RuntimeError):
        raise GraphSourceError('공유 폴더 밖의 경로 또는 심볼릭 링크는 사용할 수 없습니다.') from None
    if any(part.startswith('.') for part in normalized.parts):
        raise GraphSourceError('숨김 파일과 설정 폴더는 적재 대상에서 제외합니다.')
    if not resolved.exists():
        raise GraphSourceError('경로가 존재하지 않습니다. 공유 폴더와 입력한 경로를 확인하세요.')
    if not resolved.is_dir() and resolved.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise GraphSourceError('현재 Markdown(.md)과 텍스트(.txt) 파일을 지원합니다.')
    canonical = str(host / normalized)
    return resolved, canonical


def chunks_for(text: str) -> list[dict]:
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        chunks.append({'index': len(chunks), 'start': start, 'end': end, 'text': text[start:end]})
        if end == len(text):
            break
        start = end - CHUNK_OVERLAP
    return chunks


def document_references(text: str) -> list[tuple[str, bool]]:
    # Code samples are retained as text but do not create document links.
    prose = re.sub(r'(?m)^\s*(`{3,}|~{3,}).*?^\s*\1\s*$', '', text, flags=re.S)
    prose = re.sub(r'`[^`\n]*`|<!--.*?-->', '', prose, flags=re.S)
    refs = [(match.group(1).split('|', 1)[0].split('#', 1)[0].strip(), True)
            for match in re.finditer(r'\[\[([^\]\n]+)\]\]', prose)]
    refs += [(match.group(1), False)
             for match in re.finditer(r'(?<!!)\[[^\]\n]*\]\(\s*<?([^\s)>]+)>?(?:\s+"[^"]*")?\s*\)', prose)]
    return refs


def read_documents(path: Path) -> tuple[list[dict], dict]:
    root = SOURCE_ROOT.resolve()
    files = []
    skipped = 0
    if path.is_file():
        files = [path]
    else:
        def walk_error(_error):
            raise GraphSourceError('문서 폴더를 읽을 수 없습니다. 폴더 접근 권한을 확인하세요.')

        for directory, folders, names in os.walk(path, followlinks=False, onerror=walk_error):
            folders[:] = sorted(name for name in folders
                                if not name.startswith('.') and not (Path(directory) / name).is_symlink())
            for name in sorted(names):
                if name.startswith('.'):
                    continue
                file = Path(directory) / name
                if file.suffix.lower() in SUPPORTED_EXTENSIONS:
                    files.append(file)
                    if len(files) > MAX_FILES:
                        raise GraphSourceError('한 번에 최대 1,000개 문서를 적재할 수 있습니다. 하위 폴더를 지정하세요.')
                else:
                    skipped += 1
    documents = []
    total_bytes = 0
    for file in sorted(files):
        relative = file.relative_to(root).as_posix()
        try:
            if not file.resolve().is_relative_to(root):
                raise GraphSourceError('공유 폴더 밖을 가리키는 파일은 적재할 수 없습니다.')
            # Bound the actual read, including files that grow during ingestion.
            with file.open('rb') as stream:
                raw = stream.read(MAX_FILE_BYTES + 1)
            if len(raw) > MAX_FILE_BYTES:
                raise GraphSourceError(f'문서당 최대 2 MiB를 지원합니다: {relative}')
            total_bytes += len(raw)
            if total_bytes > MAX_TOTAL_BYTES:
                raise GraphSourceError('한 번에 최대 20 MiB를 적재할 수 있습니다. 하위 폴더를 지정하세요.')
            text = raw.decode('utf-8-sig')
            if '\x00' in text:
                raise GraphSourceError(f'텍스트 파일이 아닙니다: {relative}')
        except UnicodeError:
            raise GraphSourceError(f'UTF-8 텍스트 파일이 아닙니다: {relative}') from None
        except OSError:
            raise GraphSourceError(f'파일을 읽을 수 없습니다: {relative}') from None
        if not text.strip():
            skipped += 1
            continue
        heading = re.search(r'^#\s+(.+)$', text, flags=re.M) if file.suffix.lower() == '.md' else None
        documents.append({'path': relative, 'title': heading.group(1).strip() if heading else file.stem,
                          'text': text, 'content_hash': hashlib.sha256(raw).hexdigest(),
                          'chunks': chunks_for(text), 'references': document_references(text)
                          if file.suffix.lower() == '.md' else []})
    if not documents:
        raise GraphSourceError('적재할 문서가 없습니다. 공유 폴더에 내용이 있는 .md 또는 .txt 파일을 넣어주세요.')
    by_name = defaultdict(list)
    by_path = {doc['path']: doc for doc in documents}
    for doc in documents:
        by_name[PurePosixPath(doc['path']).stem].append(doc['path'])
    unresolved = 0
    for doc in documents:
        targets = set()
        for reference, wiki in doc.pop('references'):
            parsed = urlsplit(reference)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            target = unquote(parsed.path)
            suffix = PurePosixPath(target).suffix.lower()
            if suffix and suffix not in SUPPORTED_EXTENSIONS:
                continue
            candidates = []
            for base in (root / PurePosixPath(doc['path']).parent / target, root / target):
                for extension in ('', '.md', '.txt') if not suffix else ('',):
                    try:
                        candidates.append(Path(str(base) + extension).resolve().relative_to(root).as_posix())
                    except (OSError, ValueError):
                        continue
            resolved = next((key for key in candidates if key in by_path), None)
            if not resolved and wiki:
                names = by_name[PurePosixPath(target).stem]
                if len(names) == 1:
                    resolved = names[0]
            if resolved is None:
                unresolved += 1
            elif resolved != doc['path']:
                targets.add(resolved)
        doc['targets'] = sorted(targets)
    return documents, {'document_count': len(documents),
                       'chunk_count': sum(len(doc['chunks']) for doc in documents),
                       'link_count': sum(len(doc['targets']) for doc in documents),
                       'skipped_count': skipped, 'unresolved_link_count': unresolved}


def document_id(source_id: str, path: str) -> str:
    return hashlib.sha256(f'{source_id}\0{path}'.encode()).hexdigest()


def write_graph(tx, source: dict, documents: list[dict]) -> None:
    """Atomically publish a source snapshot. Previous content is retained inactive."""
    tx.run('MERGE (s:GraphSource {id: $id}) SET s.tenant_id = $tenant, s.name = $name, s.path = $path',
           id=source['id'], tenant=source['tenant_id'], name=source['name'], path=source['path']).consume()
    tx.run('MATCH (s:GraphSource {id: $id})-[:HAS_DOCUMENT]->(d) SET d.active = false',
           id=source['id']).consume()
    tx.run('MATCH (s:GraphSource {id: $id})-[:HAS_DOCUMENT]->(d)-[:HAS_CHUNK]->(c) SET c.active = false',
           id=source['id']).consume()
    tx.run('MATCH (s:GraphSource {id: $id})-[:HAS_DOCUMENT]->(d)-[r:LINKS_TO]->() SET r.active = false',
           id=source['id']).consume()
    rows = [{'id': document_id(source['id'], doc['path']), 'path': doc['path'],
             'title': doc['title'], 'content_hash': doc['content_hash']} for doc in documents]
    tx.run('''
        MATCH (s:GraphSource {id: $source})
        UNWIND $documents AS row
        MERGE (d:GraphDocument {id: row.id})
        SET d.source_id = $source, d.tenant_id = $tenant, d.path = row.path,
            d.title = row.title, d.content_hash = row.content_hash, d.active = true
        MERGE (s)-[:HAS_DOCUMENT]->(d)
        ''', source=source['id'], tenant=source['tenant_id'], documents=rows).consume()
    chunks = [{**chunk, 'id': f"{document_id(source['id'], doc['path'])}:{chunk['index']}",
               'document_id': document_id(source['id'], doc['path'])}
              for doc in documents for chunk in doc['chunks']]
    tx.run('''
        UNWIND $chunks AS row
        MATCH (d:GraphDocument {id: row.document_id})
        MERGE (c:GraphChunk {id: row.id})
        SET c.source_id = $source, c.tenant_id = $tenant, c.text = row.text,
            c.position = row.index, c.start = row.start, c.end = row.end, c.active = true
        MERGE (d)-[:HAS_CHUNK]->(c)
        ''', chunks=chunks, source=source['id'], tenant=source['tenant_id']).consume()
    tx.run('''
        UNWIND $chunks AS row
        MATCH (c:GraphChunk {id: row.id})
        MATCH (next:GraphChunk {id: row.document_id + ':' + toString(row.index + 1)})
        WHERE next.active = true
        MERGE (c)-[:NEXT_CHUNK]->(next)
        ''', chunks=chunks).consume()
    links = [{'from': document_id(source['id'], doc['path']), 'to': document_id(source['id'], target)}
             for doc in documents for target in doc['targets']]
    tx.run('''
        UNWIND $links AS row
        MATCH (a:GraphDocument {id: row.from}), (b:GraphDocument {id: row.to})
        MERGE (a)-[r:LINKS_TO]->(b) SET r.active = true
        ''', links=links).consume()


@lru_cache(maxsize=1)
def graph_driver():
    password = os.getenv('NEO4J_PASSWORD', '')
    if not password:
        raise GraphSourceError('Neo4j 비밀번호 설정이 없습니다.')
    return GraphDatabase.driver(os.getenv('NEO4J_URI', 'bolt://neo4j:7687'),
                                auth=(os.getenv('NEO4J_USERNAME', 'neo4j'), password),
                                connection_timeout=10, max_transaction_retry_time=15)


def ingest(source: dict) -> dict:
    path, _ = resolve_source_path(source['path'])
    documents, counts = read_documents(path)
    try:
        driver = graph_driver()
        driver.verify_connectivity()
        for label in ('GraphSource', 'GraphDocument', 'GraphChunk'):
            driver.execute_query(f'CREATE CONSTRAINT {label.lower()}_id IF NOT EXISTS '
                                 f'FOR (n:{label}) REQUIRE n.id IS UNIQUE', database_='neo4j')
        with driver.session(database='neo4j') as session:
            session.execute_write(write_graph, source, documents)
    except (Neo4jError, ServiceUnavailable, OSError):
        raise GraphSourceError('Neo4j 적재에 실패했습니다. 서버 상태와 접속 설정을 확인하세요.') from None
    return counts


def close_graph_driver():
    if graph_driver.cache_info().currsize:
        graph_driver().close()
        graph_driver.cache_clear()
