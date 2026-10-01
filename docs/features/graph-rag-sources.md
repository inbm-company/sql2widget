# 기능: 프로젝트별 Graph RAG 문서 그래프

| 항목 | 내용 |
|------|------|
| 문서명 | 기능 문서 — Graph RAG 데이터 소스 |
| 기준일 | 2026-10-01 (구현 기준) |
| 관련 문서 | [stage.md](stage.md), [admin.md](admin.md), [README.md](../../README.md), [progress.md](../progress.md) |
| 관련 코드 | `backend/app/graph_source_routes.py`, `graph_ingestion.py`, `graph_schema.py`, `graph_extraction.py`, `graph_service.py`, `graph_chat.py`, `project_graph.py`, `repositories/graph_sources.py`, `backend/sql/migrations/005_graph_sources.sql`, `006_graph_source_projects.sql`, `007_graph_source_files.sql`, `008_graph_source_schema.sql`, `009_graph_source_extraction.sql`, `frontend/src/GraphSources.jsx`, `GraphFlowCard.jsx`, `graphUpload.js`, `ProjectGraph.jsx`, `frontend/deployment/nginx.conf` |

## 범위

관리자가 브라우저에서 폴더·파일을 **업로드**하고 **적재** 버튼으로 Neo4j에 문서 본문과 문서 간 명시된 링크를 저장한다. `DB 관리`와 전체 `Admin` 패널에 표시된다. 사이드바에서 선택한 프로젝트의 데이터 소스만 등록·적재한다. Neo4j 서버는 하나를 사용하고, 테넌트·프로젝트·소스 식별자로 데이터를 논리적으로 분리한다. 프로젝트별 별도 컨테이너나 데이터베이스를 생성하지 않는다.

현재는 Graph RAG용 문서 그래프를 준비하는 단계다. 채팅 내부 설정과 질문에서 그래프를 검색하는 연결, 임베딩, 엔티티 기반 질문 검색, 자동 적재·폴더 감시, PDF·이미지 처리는 구현하지 않았다. 채팅은 기존 SQL·예상 질문 검색 경로를 유지한다.

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
- 본문은 문서 종류와 무관하게 최대 4,000자 조각으로 나누고 인접 조각은 최대 400자 겹친다. 자르는 위치는 빈 줄 → 줄바꿈 → 4,000자 순으로 가까운 곳이고, 겹침이 허용하면 다음 조각은 줄 시작에서 시작한다. Markdown 헤딩은 경계로 쓰지 않고, `.md` 조각의 `heading`(조각 시작 위치의 가까운 헤딩, 코드 블록 안 제외) 메타데이터로만 보관한다. 원문 내 시작·끝 위치도 보관한다. 엔티티 경계는 청킹이 아니라 승인된 스키마를 따르는 LLM 추출이 정한다. 이미 적재된 소스는 **다시 적재해야** 새 기준이 적용된다.
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
              unresolved_link_count, error, created_by, created_at, last_ingested_at,
              schema_draft JSONB, schema_status,  -- schema_status: none / proposed / approved
              extract_status, extract_progress JSONB, extract_error,  -- extract_status: idle / running / completed / failed
              entity_count, relation_count, last_extracted_at)
              -- path는 `upload:{id}` 식별자. 목록 응답에는 file_count가 추가된다.
graph_source_files(source_id → graph_sources ON DELETE CASCADE, path, content)
```

Neo4j 구조:

```text
(GraphSource)-[:HAS_DOCUMENT]->(GraphDocument)-[:HAS_CHUNK]->(GraphChunk)
(GraphChunk)-[:NEXT_CHUNK]->(GraphChunk)
(GraphDocument)-[:LINKS_TO]->(GraphDocument)
(Entity)-[:FROM_CHUNK]->(GraphChunk)           -- 엔티티 추출 결과. 엔티티 사이 관계는 스키마의 관계 이름
```

문서·조각 ID는 소스와 경로로 고정하며, 소스·문서·조각 노드에 `project_id`·`tenant_id`를 저장하고 문서·조각에는 `source_id`도 저장한다. 문서 링크에도 프로젝트·테넌트 범위를 저장한다. 서로 다른 소스의 링크를 합치지 않는다. 적재 시 세 노드 타입에 ID 고유 제약을 만든다.

재적재 시 같은 노드를 갱신한다. 이전 조각·문서 링크·이번에 누락된 문서는 `active=false`로 남기고 삭제하지 않는다. 이후 검색 구현은 문서·본문 조각·문서 링크의 활성 상태를 확인해야 한다.

## 엔티티 스키마 (제안·승인)

문서에서 테이블·사람 같은 **엔티티 노드**를 뽑기 전에, 어떤 타입으로 쪼갤지를 사용자와 합의하는 단계다. 현재 구현은 **스키마 제안·수정·승인 저장**까지이며, 승인된 스키마로 엔티티를 추출해 Neo4j에 적재하는 단계와 채팅에서 이를 진행하는 화면은 아직 없다.

- **제안**: 저장된 문서의 헤딩 개요와 앞부분 본문 샘플(총 12,000자 이내, 문서 최대 20개)을 채팅 LLM에 보내 `{entity_types, relation_types, questions}`를 받는다. AI 연결은 채팅과 같은 `X-LLM-*` 헤더로 전달한다. 지시문(`instruction`)과 기존 초안이 있으면 초안을 고쳐서 다시 제안한다. 호출이 실패하거나 응답이 검증을 통과하지 못하면 추측하지 않고 502로 에러를 반환하며 저장된 초안은 그대로다.
- **닫힌 타입**: 엔티티 이름은 영문 PascalCase, 관계 이름은 영문 대문자 스네이크, 속성 이름은 영문 소문자 스네이크만 허용한다(Cypher 라벨에 쓰므로 그 외 문자열 거부). 엔티티 최대 12개, 관계 최대 20개, 엔티티당 속성 최대 10개. 관계의 양끝은 선언된 엔티티여야 하고 `GraphSource`·`GraphDocument`·`GraphChunk`·`Entity`와 기존 관계 이름(`HAS_DOCUMENT` 등)은 예약어라 쓸 수 없다.
- **예시 검증**: 제안된 타입의 `examples`가 문서 본문에 실제로 있어야 한다. 문서에서 확인되지 않는 예시는 지우고, 예시가 하나도 남지 않은 타입(과 그 타입을 쓰는 관계)은 제외한 뒤 `questions`에 제외한 타입을 알린다. 모든 타입이 제외되면 502. 제안 프롬프트는 문서가 시스템 구조(DB 스키마·API·코드)를 설명하면 업무 개념(`Order`)이 아니라 구조(`Table`, `Column`)로 타입을 만들도록 지시한다.
- **되묻기**: LLM이 정하지 못한 선택(예: 컬럼을 노드로 둘지)은 `questions`(최대 3개)로 반환한다. 사용자의 답은 `instruction`으로 다시 제안받는 방식으로 반영한다.
- **상태**: `graph_sources.schema_status`는 `none`(없음) → `proposed`(초안) → `approved`(승인). 제안·수정은 항상 `proposed`로 되돌리며 `approve`로만 승인된다. 초안이 없으면 승인할 수 없다(400).
- 보관 문서를 교체해도 저장된 스키마는 유지한다.

## 엔티티 추출

승인된 스키마로 문서 조각에서 엔티티·관계를 뽑아 Neo4j에 저장하는 백그라운드 작업이다(`graph_extraction.py`).

- **전제**: 스키마가 `approved`이고 소스 상태가 `completed`(적재 완료)여야 한다. 아니면 400. 문서를 교체하면 상태가 `registered`로 돌아가므로 다시 적재해야 추출할 수 있다.
- **실행**: `extract`를 호출하면 즉시 `extract_status=running`으로 응답하고, 서버 안의 백그라운드 스레드가 조각을 하나씩 LLM에 보낸다(소스당 1개, 중복 요청은 409). 진행률은 소스의 `extract_progress`(`done`·`total`·`failed`)로 조회한다. AI 연결은 요청의 `X-LLM-*` 헤더를 쓰며 서버에 저장하지 않는다. 추출 중에는 적재·문서 교체를 409로 막는다.
- **검증**: 스키마에 없는 타입·속성은 버린다. 엔티티 이름·관계 양끝 이름·`evidence`(원문 그대로 인용)가 해당 조각 본문에 실제로 있어야 하며(Markdown 기호·대소문자·공백 차이는 무시), 없으면 버린다. 관계의 양끝 타입은 스키마 정의를 따른다. 같은 타입·이름(대소문자 무시)은 한 노드로 합치고, 관계에 나온 끝점은 엔티티로 함께 만든다.
- **실패 처리**: 조각 하나는 1회 재시도하고, 연속 3개가 실패하면 중단한다. 모든 조각이 실패해도 `failed`다. 일부만 실패하면 완료하되 `failed` 개수를 표시한다. 실패해도 이전 성공 결과(엔티티·`entity_count`)는 바뀌지 않는다. 취소(`extract/cancel`)는 현재 조각이 끝난 뒤 멈추고 마찬가지로 기존 결과를 유지한다. 서버가 재시작되면 실행 중이던 작업은 `failed`로 바뀌어 다시 실행할 수 있다.
- **저장**: 모든 조각을 처리한 뒤 Neo4j에 한 트랜잭션으로 반영한다. 노드는 `(:Entity {id, type, name, props, source_id, tenant_id, project_id, active})`(타입은 라벨이 아닌 `type` 속성), 근거는 `(Entity)-[:FROM_CHUNK {evidence}]->(GraphChunk)`, 관계는 스키마의 관계 이름 그대로다. 재추출하면 이전 엔티티·관계·근거 연결은 `active=false`로 남기고 이번 결과만 활성화한다. ID는 소스·타입·이름으로 고정이라 재실행해도 노드가 늘지 않는다.
- **검증 결과(2026-10-01, 서버 기본 AI 설정, Northwind 스키마 문서 1개)**: 제안은 `Database`·`Table`·`Column` 3타입과 `CONTAINS_TABLE`·`HAS_COLUMN`·`REFERENCES_TABLE`·`REFERENCES_COLUMN` 4관계였고, 추출은 조각 4개에서 `Table` 16개 전부와 FK 관계 13개 전부(문서 ERD와 일치)를 뽑았다. 한계: 같은 타입·이름은 문서 전체에서 한 노드로 합쳐지므로 `customer_id`처럼 여러 테이블에 있는 `Column`이 하나로 섞인다(`Column`이 55개뿐인 이유 중 하나). 컬럼은 노드가 아니라 `Table` 속성으로 두는 편이 맞을 수 있다.
- **아직 없는 것**: 엔티티를 이용한 질문 검색(`knowledge_qa` 연결), 스키마 직접 편집 화면(채팅 지시문 또는 `PUT .../schema` API로만 수정).

## 채팅 연동

문서 그래프 구성(스키마 협의·승인·추출)을 채팅에서 진행한다. 구현은 `graph_chat.py`이고 REST 라우트와 같은 로직(`graph_service.py`)을 쓴다.

- **진입**: 채팅에서 “올려둔 문서를 지식 그래프로 만들고 싶어. 어떤 노드로 나눌지 정해줘”처럼 말하면 의도 라우터가 새 경로 `graph_build`로 분류한다(Jev criteria `graph_build`, LLM 폴백도 동일). 직전 답변이 그래프 카드(`artifact.type = graph_flow`)면 라우터 입력에 `pending_graph_flow: true`를 넣어, “컬럼은 노드로 만들지 마” 같은 짧은 답도 이 경로로 가게 한다. 되묻기 버튼처럼 `route=graph_build`로 직접 요청하면 모델 호출 없이 바로 처리한다.
- **권한·대상**: 관리자만 가능하다(아니면 안내 문구). 현재 대화의 프로젝트에 올린 소스를 대상으로 하며, 소스가 없으면 올리라고 안내하고 둘 이상이면 어느 소스인지 버튼으로 되묻는다.
- **진행**: 스키마가 없으면 제안하고, 제안된 상태에서 보낸 일반 메시지는 **수정 지시**로 보고 초안을 고쳐 다시 제안한다. 답변마다 `graph_flow` 카드(엔티티 타입·예시·속성·관계·되묻는 질문)와 버튼을 붙인다. 버튼은 `graph_action = {type, source_id}`로 전송한다: `approve`(승인 후 추출), `regenerate`(처음부터 다시 제안), `extract`(다시 추출), `cancel`(추출 취소), `select`(소스 선택).
- **승인 → 추출**: `approve`는 스키마를 확정하고, 문서가 아직 적재되지 않았으면 먼저 적재한 뒤 추출 작업을 시작한다. 카드는 `GET graph-sources`를 2초마다 다시 읽어 진행률(조각 `done/total`·실패 수)과 완료 결과(엔티티·관계 수)를 보여주고, 완료되면 Stage 그래프 캐시를 갱신한다. 이미 추출이 끝난 소스에 일반 메시지를 보내면 상태만 알려 주고 스키마를 되돌리지 않는다.
- **실패 처리**: 서비스 오류(진행 중·미적재·LLM 실패 등)는 에러가 아니라 “진행하지 못했어요: …” 답변으로 돌려준다. LLM 호출 실패를 추측으로 대신하지 않는다.
- **검증(2026-10-01, 로컬 브라우저)**: 임시 프로젝트의 Northwind 문서로 자연어 요청 → 스키마 카드(3타입·4관계, 컬럼 노드 여부 질문) → “컬럼은 노드로 만들지 말고 Table의 속성으로 해줘”(2타입·2관계로 수정) → 승인 → 진행률 → 완료(엔티티 16·관계 13) → Stage 그래프 ‘엔티티’ 보기까지 확인했다. 다른 문서 유형은 아직 시험하지 않았다.

## Stage 그래프

- Stage 헤더에서 **위젯 / 그래프** 보기를 전환한다. 기존 위젯 배치·저장 동작은 유지하며 그래프는 위젯 화이트리스트나 `stage_widgets`에 추가하지 않는다.
- 현재 프로젝트의 활성 문서가 노드, 명시된 문서 링크가 방향 있는 선으로 표시된다.
- 그래프 보기 위쪽의 **문서 / 엔티티** 전환으로 두 그래프를 오간다. **엔티티** 보기는 추출된 엔티티가 노드(타입별 색, 범례에 타입별 개수), 스키마 관계가 방향 있는 선이다. 이름·타입 검색을 지원하고, 노드를 고르면 타입·속성·관계(눌러서 이동)·원문 근거(인용문과 헤딩)를 보여준다. 추출 결과가 없으면 채팅으로 만들라는 안내를 표시한다. 소유자면 Viewer에서도 조회할 수 있다. 소스·문서·본문 조각·링크 총개수를 보여준다.
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
| `POST /api/projects/{project_id}/graph-sources/{id}/schema/propose` | `{instruction?}`로 엔티티 스키마 제안(지시문이 있고 초안이 있으면 수정 제안). `X-LLM-*` 헤더 필요. 응답은 소스(`schema_draft`, `schema_status=proposed`). LLM 실패·검증 실패는 502 | admin + 소유자 |
| `PUT /api/projects/{project_id}/graph-sources/{id}/schema` | `{schema}`를 검증해 저장하고 `proposed`로 되돌림. 검증 실패는 400 | admin + 소유자 |
| `POST /api/projects/{project_id}/graph-sources/{id}/schema/approve` | 저장된 초안을 `approved`로 확정. 초안이 없으면 400 | admin + 소유자 |
| `POST /api/projects/{project_id}/graph-sources/{id}/extract` | 승인된 스키마로 엔티티 추출 작업 시작(`X-LLM-*` 헤더 필요). 스키마 미승인·미적재는 400, 이미 추출 중이면 409. 응답은 `extract_status=running`인 소스 | admin + 소유자 |
| `POST /api/projects/{project_id}/graph-sources/{id}/extract/cancel` | 실행 중인 추출을 현재 조각 뒤에 취소. 실행 중이 아니면 409 | admin + 소유자 |
| `GET /api/projects/{project_id}/graph-sources/{id}/entities?limit=500` | 활성 엔티티(`id`, `type`, `name`, `properties`)와 관계(`source`, `type`, `target`, `evidence`) 반환 | admin + 소유자 |
| `GET /api/projects/{project_id}/graph/entities?limit=500` | 프로젝트 모든 소스의 활성 엔티티(`type`, `name`, `properties`, `evidence`)와 관계 반환. Stage ‘엔티티’ 보기가 사용 | 소유자 |
| `GET /api/projects/{project_id}/graph?limit=200` | 활성 문서 노드·링크·개수·표시 제한 반환 | 소유자 |
| `GET /api/projects/{project_id}/graph/documents/{document_id}` | 소속 문서 정보와 본문 조회, 다른 프로젝트 문서는 404 | 소유자 |

이전 테넌트 공통 `/api/graph-sources` 경로는 제거했다.

기존 환경에는 `python scripts/migrate.py`를 적용한다. Docker Compose 백엔드 기동 시 이 마이그레이션을 자동 적용한다. 접속 비밀번호는 `.env`의 `NEO4J_PASSWORD`를 사용하고 API 응답·로그에 포함하지 않는다.
