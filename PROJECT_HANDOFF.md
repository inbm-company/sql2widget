# agent4any / sql2widget 인수인계

이 문서는 대화 없이 저장소만 보고 이어가기 위한 기준이다.

새 작업에서는 이렇게 요청한다.

```text
PROJECT_HANDOFF.md와 저장소를 먼저 확인하고, 기존 설계 결정을 유지하면서
미완료 작업 중 우선순위가 가장 높은 항목부터 계속 구현해줘.
```

문서 지도·공통 규칙: `AGENTS.md` / `CLAUDE.md`.  
현황: `docs/progress.md` (완료/진행중/예정/보류).  
기능 명세: `docs/features/` (구현 기준, 기능별 파일 분리).  
제품 규칙: `PRODUCT.md`. 시각: `DESIGN.md`.

---

## 1. 제품

비기술 사용자가 자연어로 고객 DB를 조회하고, 허용된 위젯으로 받은 뒤, **프로젝트마다 1개**인 Stage에 핀한다. 프로젝트는 여러 대화를 가진다.

성공은 위젯이 채팅에 나오고 몇 개를 Stage에 꽂는 것이다. 완성된 공유 대시보드 템플릿을 자동 생성하는 것은 목표가 아니다.

데모 청중은 동등하다.

| 연결 | 이름 | 데이터 |
|------|------|--------|
| `dbconn_demo` | SOC | 서버, 공격, 인시던트, 취약점, 차단 IP |
| `dbconn_global` | Global Sales | 지역, 제품, 월별 매출 |

대표 질문:

```text
지난달 공격당한 서버들의 공격 순위, 방법, 해결 방안을 보여줘.
공격 유형별 비중을 보여줘.
지역별 매출 순위를 보여줘.
```

---

## 2. 확정된 설계

- 백엔드: Python, FastAPI, `psycopg`, 순수 SQL. ORM 없음. TypeScript 없음.
- 프론트: Vite, React, JavaScript.
- 상태: fetch → `useSWR`, 전역 슬롯 → `useStore`, Provider/`SWRConfig` 금지, 입력·드래그 → `useState`.
- 로컬 기동 기준: Docker Compose.
- 스테이지는 프로젝트마다 1개. 레이아웃은 `react-grid-layout`.
- 고객 DB는 읽기 전용 `SELECT`만.
- 위젯 이름은 서버 화이트리스트. 모르는 키/차트 타입은 버린다.
- 채팅은 항상 실 LLM 호출(OpenAI-compatible/Gemini). 키 없거나 실패하면 추측 없이 에러 반환(2026-09-22, Mock 키워드 매칭 폴백 완전 삭제).
- 외부 문서는 `DocumentProvider`. 현재 구현은 Mock(문서 검색만 — 채팅 응답 자체는 Mock 아님).
- 감사 로그에는 행위만 남긴다. 사용자 데이터 수정 쿼리 없음.

---

## 3. 지금 동작하는 것

- 채팅 답변의 **처리 내역**에서 선택 경로·분류 방식과 그래프 전체/조회/전달 수, 모델이 보고한 근거 엔티티·원문을 확인한다. 표시용 `meta`는 `messages.meta`에 저장되어 새로고침 후 유지한다(`chat_trace.py`, `ChatTrace.jsx`, 마이그레이션 `010_message_meta.sql`). 과거 답변은 기록 없음이며, 조회 사실과 모델의 사용 보고를 구분한다.

- 로그인 JWT (access + refresh). admin / viewer.
- 대화 CRUD, 실 LLM 채팅 Artifact(키 필요), 샘플 질문. 프로젝트 삭제(연관 대화·Stage 정리, 문서 소스는 미연결로 보존).
- 채팅 의도 라우팅(`intent_router.py`): 요청의 `route` → TypeSafe Jev Choice(`TYPESAFE_API_KEY`) → 채팅 LLM 폴백 순으로(예상 질문 유사도는 경로 결정에 쓰지 않고 `data_query`의 SQL 계획에만 쓴다) `data_query`/`schema_qa`/`clarify`를 정한다. 확신이 `ROUTE_MIN_CONFIDENCE`(기본 0.5, 미검증 초기값) 미만이면 선택지 버튼을 반환한다. `knowledge_qa`는 프로젝트 문서의 엔티티·관계·근거로 답한다(`graph_answer.py`, `meta.knowledge`). Jev 상태의 `has_document_graph`로 문서 기반 질문과 DB 구조 질문(`schema_qa`)을 가른다. 허용 테이블이 `SCHEMA_LINK_MIN_TABLES`(기본 20)를 넘는 DB는 `data_query`에서 유사 질문이 쓴 테이블, 없으면 프로젝트 문서 그래프의 `Table` 설명에서 채팅 LLM이 고른 테이블만 스키마로 전달하고(`schema_linking.py`, `meta.schema_link`), 실패 시 복구 재시도는 전체 스키마로 한다. 운영 `compose.production.yml`은 `TYPESAFE_API_KEY`만 넘기며(비면 LLM 폴백), 나머지 `TYPESAFE_*`·`ROUTE_MIN_CONFIDENCE`는 코드 기본값을 쓴다. 상세: `docs/features/chat.md`.
- DB별 예상 질문 유사도 검색(`question_similarity.py`, `question_catalog.py`): 유사 질문이 있으면 연결된 SQL·위젯을 참조해 답한다. 상세: `docs/features/similarity-search-design.md`.
- Recharts 위젯 렌더 (KPI, 표, 순위, 막대/선/파이, PieTable, BarTable 등).
- Stage 드래그·이동·리사이즈·자동 저장·복원.
- 프로젝트별 Graph RAG 문서 업로드(브라우저 폴더·파일 선택, 서비스 DB 보관)·수동 Neo4j 적재, Stage 그래프·본문 조회. Neo4j는 한 서버에서 논리 분리한다. 이전 경로 방식 소스는 문서를 다시 올려야 적재할 수 있다. 운영 `compose.production.yml`에는 아직 Neo4j가 없어 운영에서 적재하려면 서비스 추가가 필요하다. 본문 조각은 4,000자·겹침 400자·문단 경계 우선(헤딩은 메타데이터만)이며 기존 소스는 재적재해야 반영된다. 문서 그래프 엔티티 구성은 채팅에서 진행한다: 의도 `graph_build`(`backend/app/graph_chat.py`) → LLM 스키마 제안 → 채팅으로 수정 → 승인 → 백그라운드 스레드가 LLM으로 엔티티 추출·Neo4j 적재(`X-LLM-*` 헤더) → Stage 그래프 ‘엔티티’ 보기. 핵심 로직은 `graph_service.py`를 REST와 채팅이 공유한다. Northwind 문서 1개로 실제 LLM 검증을 했고(Table 16·FK 13 추출), 같은 이름의 Column이 테이블 구분 없이 합쳐지는 한계가 있다. 질문으로 엔티티를 조회해 답하는 연동은 `knowledge_qa`로 완료됐다(`graph_answer.py`, `docs/features/chat.md`).
- Admin: 연결 등록·테스트, 역할별 테이블 권한.
- SKAX NMS 운영 DB: `compose.production.yml`의 `db-skax-nms`와 `pg_skax_nms_data`. Actions가 `backend/sql/skax_nms`의 덤프·설정 파일을 서버에 올리고 최초 볼륨에서만 복원한다. `seed_skax_nms.py`로 연결·권한 등록, `smoke_skax_nms.py`로 배포 후 읽기 전용 접속·권한 확인. 재배포로 기존 DB를 덮어쓰거나 볼륨을 삭제하지 않는다. 상세: `deployment/README.md`.
- Viewer: 채팅·DnD 없음. `/p/:id/view` 읽기 전용.
- SOC + Global Sales 샘플 DB (호스트 포트 5433, 5435). 서비스 DB 5434.
- `llm_usage` 기록 골격.

계정:

```text
admin@example.com / demo-password
viewer@example.com / demo-password
```

---

## 4. 주요 경로

```text
backend/app/main.py                 FastAPI
backend/app/auth.py                 JWT
backend/app/agent.py                위젯 화이트리스트 검증(sanitize_artifact)
backend/app/agent_service.py        LLM 실행 경로 (에러 시 예외로 502)
backend/app/intent_router.py        채팅 의도 라우팅(Jev → LLM 폴백 → 되묻기)
backend/app/question_similarity.py  예상 질문 생성·유사도 검색
backend/app/llm.py                  실모델 클라이언트
backend/app/query.py                SQL 검증, 읽기 전용 실행
backend/app/contracts.py            위젯 계약
backend/app/documents.py            Mock 문서
backend/app/repositories/           순수 SQL 저장소
backend/sql/migrations/             서비스 DB
backend/sql/sample_customer/        SOC 샘플
backend/sql/stage_global/           Global Sales 샘플
frontend/src/App.jsx                워크스페이스
backend/app/graph_source_routes.py  프로젝트 소스·그래프·엔티티 스키마 API
backend/app/graph_schema.py         엔티티 스키마 LLM 제안·검증
backend/app/graph_extraction.py     스키마대로 엔티티·관계 LLM 추출·Neo4j 반영(백그라운드)
backend/app/project_graph.py        프로젝트 범위 Neo4j 조회
frontend/src/ProjectGraph.jsx       문서 그래프·본문 조회
frontend/src/GraphSources.jsx       문서 소스 등록·업로드·적재 UI
frontend/src/StageCanvas.jsx        Stage
frontend/src/widgets/WidgetRenderer.jsx
frontend/src/store.js               SWR 래퍼
docker-compose.yml                  로컬 스택
AGENTS.md / CLAUDE.md               문서 지도·공통 규칙
docs/features/                      기능별 명세
docs/progress.md                    작업 진행 상황
PRODUCT.md
DESIGN.md
```

---

## 5. 로컬 실행

저장소:

```powershell
git clone https://github.com/inbm-company/sql2widget.git
cd sql2widget
Copy-Item .env.example .env
docker compose up --build
```

화면:

```text
Frontend  http://127.0.0.1:5173
API       http://127.0.0.1:8010
```

`.env`와 API 키는 Git에 넣지 않는다. `APP_SECRET`을 바꾸면 암호화된 연결 비밀번호를 다시 시드해야 한다.

검증:

```powershell
docker compose exec backend pytest -q
docker compose exec backend python scripts/smoke_eval.py
docker compose exec backend python scripts/smoke_stage.py
```

고객 스키마를 바꾼 뒤 볼륨이 남으면 `docker compose down -v` 후 다시 올린다.

---

## 6. API 요지

인증: `Authorization: Bearer <access>` (`/api/health`, login, refresh 제외)

```text
POST /api/auth/login
POST /api/auth/refresh
GET  /api/auth/me
GET/POST /api/projects
PATCH/DELETE /api/projects/{id}
GET  /api/conversations?project_id={id}
POST /api/conversations
GET/PATCH/DELETE /api/conversations/{id}
POST /api/chat
GET/PUT /api/projects/{id}/stage
POST /api/projects/{id}/stage/widgets
PATCH/DELETE /api/projects/{id}/stage/widgets/{widget_id}
GET/POST /api/database-connections
POST /api/database-connections/{id}/test
GET  /api/database-connections/{id}/tables
GET  /api/database-connections/{id}/questions
POST /api/database-connections/{id}/questions/search
POST /api/database-connections/{id}/questions/seed   (예상 질문, similarity-search-design.md)
POST /api/database-connections/{id}/preview-sql   (admin)
GET/PUT /api/table-permissions
GET  /api/health
```

프로젝트 문서 그래프 API(`graph-sources`, `graph`)는 `docs/features/graph-rag-sources.md`를 본다.

---

## 7. 다음 작업

우선순위는 아래 순이다. 이미 된 Admin/Viewer/Stage/연결 라우팅을 다시 만들지 않는다.

1. 질문 유사도 테스트 하니스 — 비슷한 질문이 같은 furniture를 내는지.
2. 제품 결정 — Orion 포스터 템플릿을 넣을지. 현재 규칙: 핀보드만.
3. Circle 게이지 조합 카탈로그 (ring × size × companion).
4. Viewer에 남은 다크 Orion 자리표시 정리.
5. ~~P2 실 LLM + Mock 폴백 hardening.~~ 완료(2026-09-22) — Mock 폴백은 hardening 대신 완전 삭제, 항상 실 LLM 호출 + 실패 시 에러 반환으로 정리됨.
6. 실 RAG(문서 검색 고도화), 운영 배포 (HTTPS, 백업, 강한 `APP_SECRET`, 데모 계정 제거).

---

## 8. 작업 시 주의

- 서비스 DB와 고객 DB를 섞지 않는다.
- 모델이 서비스 DB에 임의 SQL을 실행하게 하지 않는다.
- 고객 DB 비밀번호·API 키를 로그에 남기지 않는다.
- 허용 목록 밖 컴포넌트 이름을 만들지 않는다.
- 근거 없는 해결 방안을 지어내지 않는다.
- 합의 없이 DML, ORM, TypeScript, SWR Provider를 넣지 않는다.
- 완성 대시보드 템플릿을 기본 성공 조건으로 바꾸지 않는다.
