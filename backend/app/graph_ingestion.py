"""Read uploaded documents and preserve their text and explicit links in Neo4j."""

import hashlib
import os
import posixpath
import re
from collections import defaultdict
from functools import lru_cache
from pathlib import PurePosixPath
from urllib.parse import unquote, urlsplit

from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError, ServiceUnavailable

SUPPORTED_EXTENSIONS = {'.md', '.txt'}
MAX_FILES = 1000
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 20 * 1024 * 1024
CHUNK_SIZE = 4000
CHUNK_OVERLAP = 400
HEADING = re.compile(r'#{1,6}[ \t]+(\S.*)')


class GraphSourceError(ValueError):
    pass


def clean_upload_path(value) -> str:
    """Normalize an uploaded relative path; reject empty, NUL and parent-directory paths."""
    raw = str(value).replace('\\', '/').strip()
    if not raw or '\x00' in raw:
        raise GraphSourceError('파일 경로가 올바르지 않습니다.')
    parts = [part for part in PurePosixPath(raw).parts if part not in ('/', '.')]
    if not parts or '..' in parts:
        raise GraphSourceError(f'허용되지 않는 파일 경로입니다: {raw}')
    return PurePosixPath(*parts).as_posix()


def filter_upload(files: list[dict]) -> tuple[dict[str, str], int]:
    """Keep supported, non-hidden files as {path: text}; also return how many were left out."""
    kept, excluded = {}, 0
    for item in files:
        path = PurePosixPath(clean_upload_path(item['path']))
        if any(part.startswith('.') for part in path.parts) or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            excluded += 1
            continue
        kept[path.as_posix()] = item['text']
        if len(kept) > MAX_FILES:
            raise GraphSourceError('한 번에 최대 1,000개 문서를 올릴 수 있습니다. 하위 폴더를 나눠 올리세요.')
    return kept, excluded


def heading_positions(text: str) -> list[tuple[int, str]]:
    """Return (offset, title) for Markdown headings outside fenced code blocks."""
    found, fence, offset = [], None, 0
    for line in text.splitlines(keepends=True):
        stripped = line.lstrip()
        marker = stripped[:3] if stripped[:3] in ('```', '~~~') else None
        if marker and fence is None:
            fence = marker
        elif marker and marker == fence:
            fence = None
        elif fence is None and (match := HEADING.match(line.rstrip('\r\n'))):
            found.append((offset, match.group(1).strip().rstrip('#').strip()))
        offset += len(line)
    return found


def chunks_for(text: str, markdown: bool = False) -> list[dict]:
    """Split text into chunks of at most CHUNK_SIZE that overlap by up to CHUNK_OVERLAP.

    Cuts prefer a blank line, then a line break; chunks begin at a line start when the overlap allows.
    Markdown headings are recorded as `heading` metadata only and never decide where to cut.
    """
    headings = heading_positions(text) if markdown else []
    chunks, start = [], 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        if end < len(text):
            end = next((cut + len(sep) for sep in ('\n\n', '\n')
                        if (cut := text.rfind(sep, start + CHUNK_SIZE // 2, end)) != -1), end)
        current = [title for offset, title in headings if offset <= start]
        inside = [title for offset, title in headings if start < offset < end]
        chunks.append({'index': len(chunks), 'start': start, 'end': end,
                       'heading': (current or inside or [None])[-1 if current else 0], 'text': text[start:end]})
        if end == len(text):
            break
        start = end - CHUNK_OVERLAP
        line = text.find('\n', start, end)
        start = line + 1 if line != -1 else start
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


def build_documents(files: dict[str, str]) -> tuple[list[dict], dict]:
    """Turn uploaded {path: text} files into chunked documents with resolved links."""
    if len(files) > MAX_FILES:
        raise GraphSourceError('한 번에 최대 1,000개 문서를 적재할 수 있습니다. 하위 폴더를 나눠 올리세요.')
    documents = []
    skipped = 0
    total_bytes = 0
    for relative in sorted(files):
        text = files[relative]
        try:
            raw = text.encode('utf-8')
        except UnicodeError:
            raise GraphSourceError(f'UTF-8 텍스트 파일이 아닙니다: {relative}') from None
        if len(raw) > MAX_FILE_BYTES:
            raise GraphSourceError(f'문서당 최대 2 MiB를 지원합니다: {relative}')
        total_bytes += len(raw)
        if total_bytes > MAX_TOTAL_BYTES:
            raise GraphSourceError('한 번에 최대 20 MiB를 적재할 수 있습니다. 하위 폴더를 나눠 올리세요.')
        if '\x00' in text:
            raise GraphSourceError(f'텍스트 파일이 아닙니다: {relative}')
        if not text.strip():
            skipped += 1
            continue
        path = PurePosixPath(relative)
        markdown = path.suffix.lower() == '.md'
        heading = re.search(r'^#\s+(.+)$', text, flags=re.M) if markdown else None
        documents.append({'path': relative, 'title': heading.group(1).strip() if heading else path.stem,
                          'text': text, 'content_hash': hashlib.sha256(raw).hexdigest(),
                          'chunks': chunks_for(text, markdown), 'references': document_references(text) if markdown else []})
    if not documents:
        raise GraphSourceError('적재할 문서가 없습니다. 내용이 있는 .md 또는 .txt 파일을 올려 주세요.')
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
            for base in (posixpath.join(PurePosixPath(doc['path']).parent.as_posix(), target), target):
                for extension in ('', '.md', '.txt') if not suffix else ('',):
                    key = posixpath.normpath(base + extension)
                    if key != '..' and not key.startswith(('../', '/')):
                        candidates.append(key)
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
    if not source.get('project_id'):
        raise GraphSourceError('먼저 데이터 소스를 프로젝트에 연결하세요.')
    tx.run('MERGE (s:GraphSource {id: $id}) SET s.tenant_id = $tenant, s.project_id = $project, '
           's.name = $name, s.path = $path', id=source['id'], tenant=source['tenant_id'],
           project=source['project_id'], name=source['name'], path=source['path']).consume()
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
        SET d.source_id = $source, d.tenant_id = $tenant, d.project_id = $project, d.path = row.path,
            d.title = row.title, d.content_hash = row.content_hash, d.active = true
        MERGE (s)-[:HAS_DOCUMENT]->(d)
        ''', source=source['id'], tenant=source['tenant_id'], project=source['project_id'], documents=rows).consume()
    chunks = [{**chunk, 'id': f"{document_id(source['id'], doc['path'])}:{chunk['index']}",
               'document_id': document_id(source['id'], doc['path'])}
              for doc in documents for chunk in doc['chunks']]
    tx.run('''
        UNWIND $chunks AS row
        MATCH (d:GraphDocument {id: row.document_id})
        MERGE (c:GraphChunk {id: row.id})
        SET c.source_id = $source, c.tenant_id = $tenant, c.project_id = $project, c.text = row.text,
            c.position = row.index, c.start = row.start, c.end = row.end, c.heading = row.heading,
            c.active = true
        MERGE (d)-[:HAS_CHUNK]->(c)
        ''', chunks=chunks, source=source['id'], tenant=source['tenant_id'], project=source['project_id']).consume()
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
        MERGE (a)-[r:LINKS_TO]->(b)
        SET r.active = true, r.project_id = $project, r.tenant_id = $tenant
        ''', links=links, project=source['project_id'], tenant=source['tenant_id']).consume()


@lru_cache(maxsize=1)
def graph_driver():
    password = os.getenv('NEO4J_PASSWORD', '')
    if not password:
        raise GraphSourceError('Neo4j 비밀번호 설정이 없습니다.')
    return GraphDatabase.driver(os.getenv('NEO4J_URI', 'bolt://neo4j:7687'),
                                auth=(os.getenv('NEO4J_USERNAME', 'neo4j'), password),
                                connection_timeout=10, max_transaction_retry_time=15)


def ingest(source: dict, files: dict[str, str]) -> dict:
    if not source.get('project_id'):
        raise GraphSourceError('먼저 데이터 소스를 프로젝트에 연결하세요.')
    documents, counts = build_documents(files)
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
