# 기능: 프로젝트별 Graph RAG 문서 그래프

| 항목 | 내용 |
|------|------|
| 문서명 | 기능 문서 — Graph RAG 데이터 소스 |
| 기준일 | 2026-10-01 (구현 기준) |
| 관련 문서 | [stage.md](stage.md), [admin.md](admin.md), [README.md](../../README.md), [progress.md](../progress.md) |
| 관련 코드 | `backend/app/graph_source_routes.py`, `graph_ingestion.py`, `project_graph.py`, `repositories/graph_sources.py`, `backend/sql/migrations/005_graph_sources.sql`, `006_graph_source_projects.sql`, `007_graph_source_files.sql`, `frontend/src/GraphSources.jsx`, `graphUpload.js`, `ProjectGraph.jsx`, `frontend/deployment/nginx.conf` |

## 범위

관리자가 브라우저에서 폴더·파일을 **업로드**하고 **적재** 버튼으로 Neo4j에 문서 본문과 문서 간 명시된 링크를 저장한다. `DB 관리`와 전체 `Admin` 패널에 표시된다. 사이드바에서 선택한 프로젝트의 데이터 소스만 등록·적재한다. Neo4j 서버는 하나를 사용하고, 테넌트·프로젝트·소스 식별자로 데이터를 논리적으로 분리한다. 프로젝트별 별도 컨테이너나 데이터베이스를 생성하지 않는다.

현재는 Graph RAG용 문서 그래프를 준비하는 단계다. 채팅 내부 설정과 질문에서 그래프를 검색하는 연결, 임베딩, LLM 개체·관계 추출, 자동 적재·폴더 감시, PDF·이미지 처리는 구현하지 않았다. 채팅은 기존 SQL·예상 질문 검색 경로를 유지한다.

## 문서 업로드

서버 폴더 경로를 입력하지 않는다. 사용자의 컴퓨터와 서버의 경로가 달라도 동작하도록 브라우저가 파일을 읽어 올린다.

- DB 관리의 폼에서 이름을 입력하고 **폴더 선택**(하위 폴더 포함) 또는 **파일 선택**으로 문서를 고른 뒤 **문서 올리기**를 누른다.
- 브라우저가 `.md`·`.txt`만 UTF-8로 읽어 JSON(`{path, text}`)으로 전송한다. 폴더를 고르면 폴더 기준 상대 경로를 `path`로 쓴다. 숨김 폴더·파일(`.git`, `.obsidian` 등)과 미지원 파일은 올리지 않고 제외 개수를 보여준다.
- 서버는 경로를 정규화하고(`..`·빈 경로 거부) 같은 규칙으로 다시 걸러낸 뒤, 적재와 같은 검사(크기·UTF-8·빈 문서)를 통과해야 저장한다. 검사에 실패하면 아무것도 저장하지 않고 400을 반환한다.
- 올린 문서는 서비스 DB의 `graph_source_files`에 **보관**한다. 업로드는 적재를 실행하지 않으며, 목록의 **적재** 버튼이 보관된 문서를 Neo4j에 저장한다.
- 문서를 고쳤다면 소스의 **폴더/파일 다시 올리기**로 보관 문서를 통째로 교체한다. 교체하면 상태가 `registered`로 돌아가며 **적재**를 눌러야 그래프에 반영된다.
- 같은 이름으로 여러 번 올리면 각각 별도 소스가 된다. 서버의 임의 경로를 읽지 않으므로 공유 폴더 마운트와 `GRAPH_RAG_HOST_PATH`는 없다.
- 업로드 본문은 최대 20 MiB이며 운영 nginx는 이 API 경로에 한해 32 MB까지 허용한다(`frontend/deployment/nginx.conf`, `deployment/sql2widget.crudy.cloud.conf`).

## 이전 경로 방식 소스

이전 버전에서 경로로 등록한 소스는 행이 그대로 남지만 보관된 문서가 없다(목록에 "올린 문서 없음" 표시, **적재** 비활성). 문서를 다시 올리면 같은 소스로 적재할 수 있다. 경로 등록·`assign`(프로젝트 연결) API는 제거했으며, 프로젝트에 연결되지 않은 이전 소스는 목록에 표시하지 않는다. 이미 Neo4j에 저장된 데이터는 삭제하지 않는다.

## 수동 적재

지원: UTF-8 Markdown(`.md`)·텍스트(`.txt`). 폴더는 하위 폴더까지 올린다.

- 숨김 파일·폴더(`.obsidian`, `.git` 등)는 올리지 않는다. 이미지·PDF 등 미지원 파일은 업로드 때 제외 개수를 보여주고, 빈 문서는 적재 결과에 제외 개수로 표시한다.
- 적재할 문서가 없거나 UTF-8이 아니면 실패로 표시한다. 에러를 완료로 표시하지 않는다.
- 제한: 문서당 2 MiB, 한 번에 1,000개 문서·20 MiB. 초과하면 작은 하위 폴더로 나눠 올린다.
- 본문은 4,000자 단위로 나누고 인접 조각은 400자를 겹친다. 원문 내 시작·끝 위치를 보관한다.
- Markdown의 Obsidian `[[문서]]`, `[[문서#제목|표시명]]`, 일반 상대 링크를 실제 적재 문서에 연결한다. 코드 예제·외부 URL·이미지 링크는 문서 관계를 만들지 않는다.
- 같은 파일명의 후보가 여러 개이거나 대상이 없는 링크는 임의로 연결하지 않고 미해결 링크 개수를 표시한다. 업로드한 상대 경로·파일명으로 해석하며 Obsidian frontmatter 별칭은 해석하지 않는다.
- 결과에 문서·본문 조각·문서 링크·제외 파일·미해결 링크 수, 마지막 성공 시각을 표시한다. 실패해도 직전 성공 결과는 유지한다.

상태: `registered`(등록됨) → `processing`(적재 중) → `completed`(적재 완료) 또는 `failed`(적재 실패).

적재 요청은 동기 실행하고 화면은 처리 중 상태를 조회한다. 소스별 PostgreSQL 세션 잠금으로 중복 실행을 409로 거부한다. 백엔드가 중단되면 잠금이 풀리므로 버튼으로 다시 실행할 수 있다. Neo4j 반영은 소스 전체를 한 트랜잭션으로 처리한다. 서비스 DB와 Neo4j 사이에는 분산 트랜잭션이 없으므로 결과 상태 저장에 실패한 경우 재실행으로 복구한다.

## 저장 구조

소스 상태와 올린 문서는 **서비스 PostgreSQL**의 `graph_sources`·`graph_source_files`에 저장한다. 고객 PostgreSQL 데이터는 읽거나 수정하지 않는다. 소스 업로드·목록·교체·적재는 관리자이면서 해당 프로젝트 소유자인 사용자만 가능하다. 그래프·문서 조회는 로그인한 프로젝트 소유자에게 허용한다(viewer 포함). API는 프로젝트 소유자·테넌트를 검사한 뒤 서비스 DB에서 소스 ID를 구하고, Neo4j에서도 테넌트·프로젝트·소스·활성 상태를 모두 검사한다.

```text
graph_sources(id, tenant_id, project_id?, name, path, status,
              document_count, chunk_count, link_count, skipped_count,
              unresolved_link_count, error, created_by, created_at, last_ingested_at)
              -- path는 `upload:{id}` 식별자. 목록 응답에는 file_count가 추가된다.
graph_source_files(source_id → graph_sources ON DELETE CASCADE, path, content)
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
- 제목·경로 검색, 확대·축소·전체 보기, 배경 드래그 이동을 지원한다. 휠은 마우스 위치를 중심으로 확대·축소하며 확대 범위는 10%~3200%다. 노드와 제목 공간을 분리해 문서가 많아도 겹치지 않도록 배치한다. 노드는 클릭하거나 키보드 Enter/Space로 선택한다.
- 선택한 문서의 소스·경로·본문 조각 수·본문을 보여주고 연결된 문서로 이동할 수 있다. 본문은 조각 겹침을 제거한 일반 텍스트로 표시한다(HTML 실행 없음).
- 문서 기본 200개(API 상한 500개), 표시된 문서 사이 링크 최대 1,000개를 반환한다. 초과 시 제한 안내를 표시하며 검색은 표시된 문서를 대상으로 한다. 본문은 처음 100,000자까지 보여준다.
- 적재 후 그래프 캐시를 갱신한다. Stage의 **새로고침**으로 다시 조회할 수도 있다. 문서가 없거나 조회에 실패하면 안내·오류를 표시한다.
- Viewer에서도 그래프·본문 조회가 가능하다. 프로젝트 소유자 검사는 동일하며 소스 편집은 제공하지 않는다.

## API

아래 경로의 `{project_id}`는 로그인한 사용자가 소유한 프로젝트여야 한다.

| API | 동작 | 권한 |
|-----|------|------|
| `GET /api/projects/{project_id}/graph-sources` | 해당 프로젝트 소스(`file_count` 포함), 지원 확장자 | admin + 소유자 |
| `POST /api/projects/{project_id}/graph-sources` | `{name, files:[{path, text}]}` 업로드로 새 소스 생성·문서 보관. 응답에 `excluded_count` | admin + 소유자 |
| `PUT /api/projects/{project_id}/graph-sources/{id}/files` | `{files}`로 보관 문서를 교체하고 상태를 `registered`로 되돌림 | admin + 소유자 |
| `POST /api/projects/{project_id}/graph-sources/{id}/ingest` | 보관된 문서를 읽어 Neo4j에 적재하고 결과 반환 | admin + 소유자 |
| `GET /api/projects/{project_id}/graph?limit=200` | 활성 문서 노드·링크·개수·표시 제한 반환 | 소유자 |
| `GET /api/projects/{project_id}/graph/documents/{document_id}` | 소속 문서 정보와 본문 조회, 다른 프로젝트 문서는 404 | 소유자 |

이전 테넌트 공통 `/api/graph-sources` 경로는 제거했다.

기존 환경에는 `python scripts/migrate.py`를 적용한다. Docker Compose 백엔드 기동 시 이 마이그레이션을 자동 적용한다. 접속 비밀번호는 `.env`의 `NEO4J_PASSWORD`를 사용하고 API 응답·로그에 포함하지 않는다.
