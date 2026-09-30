# 기능: 프로젝트별 Graph RAG 문서 그래프

| 항목 | 내용 |
|------|------|
| 문서명 | 기능 문서 — Graph RAG 데이터 소스 |
| 기준일 | 2026-09-30 (구현 기준) |
| 관련 문서 | [stage.md](stage.md), [admin.md](admin.md), [README.md](../../README.md), [progress.md](../progress.md) |
| 관련 코드 | `backend/app/graph_source_routes.py`, `graph_ingestion.py`, `project_graph.py`, `repositories/graph_sources.py`, `backend/sql/migrations/005_graph_sources.sql`, `006_graph_source_projects.sql`, `frontend/src/GraphSources.jsx`, `ProjectGraph.jsx`, `docker-compose.yml` |

## 범위

관리자가 로컬 폴더·파일 경로를 등록하고 **적재** 버튼으로 Neo4j에 문서 본문과 문서 간 명시된 링크를 저장한다. `DB 관리`와 전체 `Admin` 패널에 표시된다. 사이드바에서 선택한 프로젝트의 데이터 소스만 등록·적재한다. Neo4j 서버는 하나를 사용하고, 테넌트·프로젝트·소스 식별자로 데이터를 논리적으로 분리한다. 프로젝트별 별도 컨테이너나 데이터베이스를 생성하지 않는다.

현재는 Graph RAG용 문서 그래프를 준비하는 단계다. 채팅 내부 설정과 질문에서 그래프를 검색하는 연결, 임베딩, LLM 개체·관계 추출, 자동 적재·폴더 감시, PDF·이미지 처리는 구현하지 않았다. 채팅은 기존 SQL·예상 질문 검색 경로를 유지한다.

## 경로 등록

- `.env`의 `GRAPH_RAG_HOST_PATH`로 공유할 **호스트 폴더**를 지정한다. 기본값은 `./graph-rag-sources`다.
- Docker 백엔드에는 `/graph-rag-sources`로 **읽기 전용** 마운트한다. 공유 폴더 변경 시 백엔드 컨테이너를 재생성한다.
- 폼에는 이름과 폴더·파일 경로를 입력한다. 호스트 공유 폴더의 절대 경로, 컨테이너 공유 경로, 공유 폴더 내부 상대 경로를 받는다.
- 존재하는 경로만 등록한다. 공유 범위를 벗어난 경로, `..` 탈출, 숨김 경로, 범위 밖으로 연결되는 심볼릭 링크는 거부한다.
- 빈 폴더도 등록할 수 있다. 같은 프로젝트의 같은 정규화 경로를 재등록하면 이름만 갱신한다.
- 경로 등록은 적재를 실행하지 않는다. 새로고침 후에도 등록 목록이 유지된다.

## 기존 소스 연결

마이그레이션 `006_graph_source_projects.sql`은 기존 소스를 삭제하거나 임의 프로젝트에 배정하지 않는다. `project_id=NULL`로 보존하고 생성자에게 **프로젝트에 연결되지 않은 기존 소스**로 표시한다.

- 사용할 프로젝트를 선택한 뒤 DB 관리에서 **이 프로젝트에 연결**을 누른다. 기존 Neo4j 문서·조각·링크에 프로젝트 범위를 추가하고 서비스 DB에 소속을 저장한다. 문서 ID와 본문을 보존한다.
- 같은 경로가 이미 해당 프로젝트에 있으면 409로 거부한다. 연결된 소스를 다른 프로젝트로 옮기는 UI·API는 없다.
- 프로젝트가 삭제되면 서비스 DB의 소스는 미연결 상태로 남는다(`ON DELETE SET NULL`). 그래프 기록은 삭제하지 않고 생성자가 새 프로젝트를 선택해 다시 연결할 수 있다.
- 소스가 서로 다른 프로젝트에 따로 등록되면 같은 경로도 서로 다른 소스·문서 ID로 적재된다.

## 수동 적재

지원: UTF-8 Markdown(`.md`)·텍스트(`.txt`). 폴더는 하위 폴더까지 읽는다.

- 숨김 파일·폴더(`.obsidian`, `.git` 등)와 심볼릭 링크 폴더는 탐색하지 않는다.
- 이미지·PDF 등 미지원 파일과 빈 문서는 제외 개수를 표시한다.
- 적재할 문서가 없거나, 파일을 읽을 수 없거나, UTF-8이 아니면 실패로 표시한다. 에러를 완료로 표시하지 않는다.
- 제한: 문서당 2 MiB, 한 번에 1,000개 문서·20 MiB. 초과하면 작은 하위 폴더를 지정한다.
- 본문은 4,000자 단위로 나누고 인접 조각은 400자를 겹친다. 원문 내 시작·끝 위치를 보관한다.
- Markdown의 Obsidian `[[문서]]`, `[[문서#제목|표시명]]`, 일반 상대 링크를 실제 적재 문서에 연결한다. 코드 예제·외부 URL·이미지 링크는 문서 관계를 만들지 않는다.
- 같은 파일명의 후보가 여러 개이거나 대상이 없는 링크는 임의로 연결하지 않고 미해결 링크 개수를 표시한다. 파일명·상대 경로로 해석하며 Obsidian frontmatter 별칭은 해석하지 않는다.
- 결과에 문서·본문 조각·문서 링크·제외 파일·미해결 링크 수, 마지막 성공 시각을 표시한다. 실패해도 직전 성공 결과는 유지한다.

상태: `registered`(등록됨) → `processing`(적재 중) → `completed`(적재 완료) 또는 `failed`(적재 실패).

적재 요청은 동기 실행하고 화면은 처리 중 상태를 조회한다. 소스별 PostgreSQL 세션 잠금으로 중복 실행을 409로 거부한다. 백엔드가 중단되면 잠금이 풀리므로 버튼으로 다시 실행할 수 있다. Neo4j 반영은 소스 전체를 한 트랜잭션으로 처리한다. 서비스 DB와 Neo4j 사이에는 분산 트랜잭션이 없으므로 결과 상태 저장에 실패한 경우 재실행으로 복구한다.

## 저장 구조

경로·상태는 **서비스 PostgreSQL**의 `graph_sources`에 저장한다. 고객 PostgreSQL 데이터는 읽거나 수정하지 않는다. 소스 등록·목록·연결·적재는 관리자이면서 해당 프로젝트 소유자인 사용자만 가능하다. 그래프·문서 조회는 로그인한 프로젝트 소유자에게 허용한다(viewer 포함). API는 프로젝트 소유자·테넌트를 검사한 뒤 서비스 DB에서 소스 ID를 구하고, Neo4j에서도 테넌트·프로젝트·소스·활성 상태를 모두 검사한다.

```text
graph_sources(id, tenant_id, project_id?, name, path, status,
              document_count, chunk_count, link_count, skipped_count,
              unresolved_link_count, error, created_by, created_at, last_ingested_at)
```

Neo4j 구조:

```text
(GraphSource)-[:HAS_DOCUMENT]->(GraphDocument)-[:HAS_CHUNK]->(GraphChunk)
(GraphChunk)-[:NEXT_CHUNK]->(GraphChunk)
(GraphDocument)-[:LINKS_TO]->(GraphDocument)
```

문서·조각 ID는 소스와 경로로 고정하며, 소스·문서·조각 노드에 `project_id`·`tenant_id`를 저장하고 문서·조각에는 `source_id`도 저장한다. 문서 링크에도 프로젝트·테넌트 범위를 저장한다. 서로 다른 소스의 링크를 합치지 않는다. 적재 시 세 노드 타입에 ID 고유 제약을 만든다.

재적재 시 같은 노드를 갱신한다. 이전 조각·문서 링크·이번에 누락된 문서는 `active=false`로 남기고 삭제하지 않는다. 이후 검색 구현은 문서·본문 조각·문서 링크의 활성 상태를 확인해야 한다.

## Stage 그래프

- Stage 헤더에서 **위젯 / 그래프** 보기를 전환한다. 기존 위젯 배치·저장 동작은 유지하며 그래프는 위젯 화이트리스트나 `stage_widgets`에 추가하지 않는다.
- 현재 프로젝트의 활성 문서가 노드, 명시된 문서 링크가 방향 있는 선으로 표시된다. 소스·문서·본문 조각·링크 총개수를 보여준다.
- 제목·경로 검색, 확대·축소·전체 보기, 배경 드래그 이동을 지원한다. 노드는 클릭하거나 키보드 Enter/Space로 선택한다.
- 선택한 문서의 소스·경로·본문 조각 수·본문을 보여주고 연결된 문서로 이동할 수 있다. 본문은 조각 겹침을 제거한 일반 텍스트로 표시한다(HTML 실행 없음).
- 문서 기본 200개(API 상한 500개), 표시된 문서 사이 링크 최대 1,000개를 반환한다. 초과 시 제한 안내를 표시하며 검색은 표시된 문서를 대상으로 한다. 본문은 처음 100,000자까지 보여준다.
- 적재·기존 소스 연결 후 그래프 캐시를 갱신한다. Stage의 **새로고침**으로 다시 조회할 수도 있다. 문서가 없거나 조회에 실패하면 안내·오류를 표시한다.
- Viewer에서도 그래프·본문 조회가 가능하다. 프로젝트 소유자 검사는 동일하며 소스 편집은 제공하지 않는다.

## API

아래 경로의 `{project_id}`는 로그인한 사용자가 소유한 프로젝트여야 한다.

| API | 동작 | 권한 |
|-----|------|------|
| `GET /api/projects/{project_id}/graph-sources` | 해당 프로젝트 소스, 본인이 만든 미연결 소스, 공유 루트, 지원 확장자 | admin + 소유자 |
| `POST /api/projects/{project_id}/graph-sources` | `{name, path}` 등록 또는 같은 프로젝트·경로의 이름 갱신 | admin + 소유자 |
| `POST /api/projects/{project_id}/graph-sources/{id}/assign` | 본인이 만든 미연결 소스를 프로젝트에 연결 | admin + 소유자 |
| `POST /api/projects/{project_id}/graph-sources/{id}/ingest` | 프로젝트 문서를 읽어 Neo4j에 적재하고 결과 반환 | admin + 소유자 |
| `GET /api/projects/{project_id}/graph?limit=200` | 활성 문서 노드·링크·개수·표시 제한 반환 | 소유자 |
| `GET /api/projects/{project_id}/graph/documents/{document_id}` | 소속 문서 정보와 본문 조회, 다른 프로젝트 문서는 404 | 소유자 |

이전 테넌트 공통 `/api/graph-sources` 경로는 제거했다.

기존 환경에는 `python scripts/migrate.py`를 적용한다. Docker Compose 백엔드 기동 시 이 마이그레이션을 자동 적용한다. 접속 비밀번호는 `.env`의 `NEO4J_PASSWORD`를 사용하고 API 응답·로그에 포함하지 않는다.
