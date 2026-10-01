# 폴더 구조 문서

| 항목 | 내용 |
|------|------|
| 문서명 | 폴더 구조 문서 |
| 기준일 | 2026-10-01 |
| 관련 문서 | [AGENTS.md](../AGENTS.md) / [CLAUDE.md](../CLAUDE.md)(공통 규칙), [docs/features/*.md](features)(기능별 상세) |

이 문서는 저장소의 폴더·파일이 각각 무엇을 하는지 설명한다. 함수 단위 설명은 다루지 않는다 — 그건 `docs/features/*.md`와 코드 자체가 기준이다. 포트 번호, 환경변수 값 같은 구체 수치는 `docker-compose.yml` / `.env.example`이 원본이며, 여기서는 파일이 하는 역할만 적는다.

---

## 1. 최상위 구조

```text
sql2widget/
├── AGENTS.md, CLAUDE.md        에이전트용 프로젝트 문서(공통 규칙, 자동 로드)
├── README.md                   로컬 실행/스모크 테스트
├── PRODUCT.md                  제품 정의
├── DESIGN.md                   디자인 시스템
├── PROJECT_HANDOFF.md          인수인계 요약
├── docker-compose.yml          로컬 개발 스택
├── compose.production.yml      운영 스택
├── .env.example                환경변수 템플릿
├── backend/                    FastAPI 서버
├── frontend/                   Vite + React 앱
├── deployment/                 운영 배포 설정·문서
├── docs/                       문서 모음 (본 문서 포함)
├── scripts/                    저장소 루트 유틸 스크립트 (배포용)
├── .github/workflows/          CI/CD (GitHub Actions)
├── .agents/skills/              코딩 에이전트용 스킬 정의 (앱 코드 아님)
└── .impeccable/                 디자인 토큰 원본 (design.json, DESIGN.md 생성 소스로 추정)
```

---

## 2. `backend/` — FastAPI 서버

```text
backend/
├── app/                 애플리케이션 코드
├── scripts/             마이그레이션·시드·스모크 스크립트
├── sql/                 DB별 SQL 마이그레이션/시드 원본
├── tests/               pytest 단위 테스트
├── evals/               에이전트 응답 품질 평가 데이터
├── Dockerfile
└── requirements.txt
```

### 2.1 `backend/app/` — 핵심 모듈

| 파일 | 역할 |
|------|------|
| `main.py` | FastAPI 앱 엔트리포인트. `/api/*` 라우트 정의 (auth, projects, conversations, chat, database-connections, 예상 질문, table-permissions, stage). 프로젝트 문서 그래프 라우트는 `graph_source_routes.py`를 include |
| `config.py` | 환경변수 로드(`env()`), DB URL들, JWT 만료시간, `ALLOWED_COMPONENTS` 화이트리스트 정의 |
| `auth.py` | 비밀번호 해시(argon2), JWT access/refresh 발급·검증, `get_current_user` 의존성 |
| `contracts.py` | API 요청/응답 Pydantic 모델 (`LoginRequest`, `ChatRequest`, `StageWidgetIn` 등) |
| `db.py` | 서비스 DB 커넥션 컨텍스트매니저, `fetch_one`/`fetch_all`/`execute` 헬퍼 |
| `crypto.py` | `APP_SECRET` 기반 Fernet 암호화 — DB 연결 비밀번호 저장용 |
| `query.py` | 고객 DB용 읽기 전용 SQL 검증·실행. `SELECT`/`WITH` 외 차단, 허용 테이블 검사, 결과 JSON 직렬화 |
| `agent.py` | 위젯 Artifact 정리(`sanitize_artifact`) — 화이트리스트 밖 컴포넌트·키 제거. 예전 Mock 키워드 에이전트는 삭제됨 |
| `local_models.py` | 로컬(OpenAI 호환) 서버 `/models` 조회. `POST /api/ai/local-models`(관리자 전용)가 호출 |
| `agent_service.py` | 실 LLM 경로 오케스트레이터. `run_agent()`가 `main.py`의 `/api/chat`에서 호출되며 의도 라우팅 결과에 따라 데이터 조회/구조 답변/되묻기로 분기 |
| `schema_linking.py` | 큰 DB의 SQL 계획 스키마 줄이기 — 유사 질문이 쓴 테이블, 없으면 문서 그래프의 테이블 설명으로 고른 테이블만 전달, 실패 시 전체로 승격 |
| `chat_trace.py` | 채팅 응답의 표시용 처리 내역을 허용된 필드만 추려 저장(API 키·원시 오류·SQL 계획 제외) |
| `intent_router.py` | 채팅 의도 라우팅 — Jev Choice 분류(재시도 포함), 실패 시 채팅 LLM 판단, 낮은 확신은 되묻기 |
| `question_similarity.py` | DB 전체 예상 질문 생성과 역할(테이블 권한) 안전한 유사도 검색 |
| `graph_ingestion.py` | 업로드된 문서를 읽어 문단 우선 본문 조각·명시된 문서 링크를 Neo4j에 적재(파일 수·크기 제한 포함) |
| `graph_schema.py` | 문서 그래프 엔티티 스키마 — 채팅 LLM 제안, 닫힌 타입 검증(이름 형식·개수·예약어) |
| `graph_service.py` | 문서 소스 작업(적재·스키마 제안/승인·추출 시작/취소)의 공통 로직. REST 라우트와 채팅이 함께 사용 |
| `graph_answer.py` | 채팅 `knowledge_qa` 경로 — 프로젝트 문서의 엔티티·관계·근거로 답변과 근거 위젯을 만든다(고정 Cypher로 읽기, 40개 초과 시 LLM으로 좁히기) |
| `graph_chat.py` | 채팅 `graph_build` 경로 — 스키마 협의·승인·추출을 대화로 진행하고 `graph_flow` 카드·버튼을 반환 |
| `graph_extraction.py` | 승인된 스키마로 조각에서 엔티티·관계를 LLM 추출(근거 인용 검증)하고 Neo4j에 반영하는 백그라운드 작업 |
| `project_graph.py` | 프로젝트 범위 Neo4j 그래프·문서 본문 조회, 기존 소스의 프로젝트 연결 |
| `graph_source_routes.py` | 문서 소스 등록·연결·적재, 그래프·문서 조회 API 라우터 |
| `llm.py` | 공통 AI 진입점 (`plan_with_llm`, `embed_text`, `embed_texts`), 오류·사용량 기록 |
| `prompts.py` | SQL·위젯 계획 및 예상 질문 생성 공통 프롬프트 |
| `providers/` | `__init__.py`: Provider 선택·설정, `openai.py`: OpenAI 호환 요청·응답, `gemini.py`: Gemini 설정, `local.py`: 로컬 요청·임베딩 차원 검사, `transport.py`: 공통 HTTP 전송 |
| `documents.py` | `DocumentProvider` 프로토콜 + Mock 구현. 해결 방안 텍스트에 쓰이는 문서 출처 검색 |

### 2.2 `backend/app/repositories/` — 순수 SQL 저장소 (ORM 없음)

| 파일 | 역할 |
|------|------|
| `projects.py` | `projects` 테이블 CRUD, 프로젝트 삭제(연관 대화·Stage 정리, 문서 소스는 미연결로 보존) |
| `conversations.py` | `conversations` + `messages` CRUD, 제목 자동 갱신 |
| `stages.py` | `stages` + `stage_widgets` CRUD, 컴포넌트 화이트리스트 검증 |
| `connections.py` | `database_connections`(암호화 저장) + `table_permissions` CRUD, 연결 URL 조립 |
| `message_embeddings.py` | 채팅 메시지 임베딩 저장/유사도 검색 (pgvector, 별도 `chat_vector` DB) |
| `question_catalog.py` | DB별 예상 질문과 연결 SQL·위젯 정보 저장/검색(채팅 이력과 분리) |
| `graph_sources.py` | 프로젝트별 Graph RAG 문서 소스(경로·업로드 파일·적재 상태) 저장 |

### 2.3 `backend/scripts/` — 운영/개발 스크립트

| 파일 | 역할 |
|------|------|
| `migrate.py` | 서비스 DB(`backend/sql/migrations/`) 마이그레이션 적용 |
| `migrate_customer.py` | SOC 샘플 고객 DB(`backend/sql/sample_customer/`) 마이그레이션 |
| `migrate_stage_global.py` | Global Sales 샘플 DB(`backend/sql/stage_global/`) 마이그레이션 |
| `migrate_northwind.py` | Northwind 샘플 DB 적용 + 운영 날짜 필드 최근화 |
| `migrate_chat_vector.py` | pgvector 확장 + `message_embeddings` 마이그레이션 |
| `seed_dev.py` | 데모 테넌트, admin/viewer 계정, DB 연결, 권한, Mock 문서 시드 |
| `seed_northwind_recent.py` | Northwind에 결정론적 "최근 운영 데이터" 델타 생성 |
| `seed_skax_nms.py` | 복원된 SKAX NMS DB를 연결로 등록하고 `cinamon` 스키마 테이블 권한 허용 |
| `smoke_chat_e2e.py` | 실행 중인 API에 대한 채팅 E2E 스모크 |
| `smoke_eval.py` | 로그인 + SOC 샘플 질문 스모크. 기본은 실모델 위젯 생성, `--expect-ai-error`는 AI 미설정 HTTP 502 검증 (evals/questions.json과 별개의 빠른 점검) |
| `smoke_stage.py` | Stage 위젯 추가/조회 스모크 |
| `smoke_skax_nms.py` | 등록된 SKAX 연결의 읽기 전용 접속·cinamon 테이블/뷰·역할별 권한 확인. 운영 배포 완료 전 실행 |

### 2.4 `backend/sql/` — DB별 SQL 원본

| 폴더 | 대상 DB | 내용 |
|------|---------|------|
| `migrations/` | 서비스 DB | `users`, `projects`, `conversations`, `stages`, `database_connections` 등 스키마 |
| `sample_customer/` | SOC 데모 DB (`dbconn_demo`) | `servers`, `attack_events`, `incidents`, `vulnerability_findings`, `blocked_ips` |
| `stage_global/` | Global Sales 데모 DB (`dbconn_global`) | `regions`, `products`, `monthly_sales` |
| `northwind/` | Northwind 샘플 DB | 표준 Northwind 스키마 + 최근 운영 데이터 델타 |
| `skax_nms/` | SKAX NMS 샘플 DB | 복원된 전체 덤프(`cinamon` 스키마), 로컬 설정 스크립트 |
| `chat_vector/` | 채팅 임베딩 DB | pgvector 확장, `message_embeddings` 테이블 |

서비스 DB 마이그레이션은 `001_initial` ~ `010_message_meta`(프로젝트, 뷰어 역할, Graph RAG 소스·업로드 파일·엔티티 스키마·추출 상태·채팅 처리 내역 포함)까지 있다.

### 2.5 나머지

- `backend/tests/` — pytest. `test_local_models.py`(로컬 모델 목록 조회), `test_chat_trace.py`(처리 내역 필터·API 저장/조회), `test_conversations.py`, `test_projects.py`(삭제 포함), `test_query.py`(SQL 검증), `test_llm_runtime.py`(LLM 경로), `test_schema_context.py`(권한 테이블 → LLM 스키마 컨텍스트), `test_intent_router.py`(의도 라우팅), `test_schema_linking.py`(스키마 줄이기), `test_graph_answer.py`(문서 그래프 답변), `test_question_catalog.py`·`test_question_similarity.py`(예상 질문), `test_graph_sources.py`(문서 소스·그래프).
- `frontend/tests/` — Node 단위 테스트. `chatTrace.test.js`(조회·전달·복구 상태 구분), `aiSettings.test.js`, `graphLayout.test.js`, `graphViewport.test.js`, `graphUpload.test.js`.
- `backend/evals/questions.json` — 질문별 기대 Artifact 형태(컴포넌트, 최소 위젯 수)를 정의한 평가 데이터셋.
- `backend/Dockerfile`, `backend/.dockerignore` — 백엔드 컨테이너 빌드.

---

## 3. `frontend/` — Vite + React (JavaScript)

```text
frontend/
├── src/
├── deployment/nginx.conf     운영용 정적 서빙 + /api 프록시 설정
├── Dockerfile / Dockerfile.production
├── index.html
└── vite.config.js
```

### 3.1 `frontend/src/`

| 파일 | 역할 |
|------|------|
| `main.jsx` | React 진입점. `BrowserRouter`로 `App`을 마운트 |
| `App.jsx` | 워크스페이스 최상위 컴포넌트. 로그인, 사이드바, 채팅(되묻기 선택지 포함), 라우팅(`/`, `/p/:id/view`)을 모두 포함하는 가장 큰 파일 |
| `StageCanvas.jsx` | Stage 핀보드. `react-grid-layout` 기반 드래그·리사이즈·자동 저장, `addWidgetToStage` export |
| `ViewerStagePage.jsx` | `/p/:projectId/view` 라우트. `StageCanvas`를 읽기 전용으로 감싸는 얇은 래퍼 |
| `AdminPanel.jsx` | 관리자 드로어 — DB 연결 등록/테스트, AI 설정, 테이블 권한 |
| `ChatTrace.jsx` | 답변의 선택 경로·그래프 조회/전달 수·모델 사용 보고와 원문 근거를 펼쳐 표시 |
| `chatTrace.js` | 처리 경로 이름과 실제 그래프 사용 상태의 표시 문구 |
| `GraphSources.jsx` | DB 관리 패널의 Graph RAG 문서 소스 등록·업로드·적재 UI |
| `ProjectGraph.jsx` | Stage의 프로젝트 문서 그래프·본문 조회 (Viewer 포함) |
| `graphLayout.js` | 그래프 노드 배치(겹침 방지) 계산 |
| `graphViewport.js` | 그래프 확대·축소 범위(10%~3200%)와 마우스 기준 줌 계산 |
| `graphUpload.js` | 브라우저 폴더·파일 선택을 업로드 대상으로 정리 |
| `widgets/WidgetRenderer.jsx` | 위젯 컴포넌트 렌더러. `component` 이름별로 Recharts 차트/표/KPI 등을 그림 |
| `sqlHelpers.js` | 어떤 컴포넌트가 SQL 보기를 지원하는지(`canShowSql`), 위젯에서 실행 SQL을 뽑는 로직(`resolveWidgetSql`) |
| `store.js` | 상태관리 3원칙의 구현부. `useStore`(SWR 캐시 기반 전역 슬롯), `storeKeys`(SWR 키 레지스트리) |
| `api.js` | 백엔드 API 클라이언트. 토큰 저장/갱신(`localStorage`), AI 설정 헤더 전달, 401 시 refresh 재시도 |
| `aiSettings.js` | Provider별 브라우저 AI 설정 저장·복원, 기존 설정 호환 |
| `constants.js` | 데이터셋별 샘플 질문 목록 (SOC/Global/Northwind) |
| `styles.css` | 전역 스타일. 토큰은 `DESIGN.md` 기준 |

---

## 4. 배포 / 인프라

| 경로 | 역할 |
|------|------|
| `docker-compose.yml` | 로컬 개발 스택 (frontend, backend, 서비스 DB, 샘플 고객 DB들) |
| `compose.production.yml` | 운영 스택. SKAX 스냅샷을 별도 DB·영속 볼륨으로 복원·등록. DB/API는 외부 포트를 열지 않고 프런트만 리버스 프록시로 노출 |
| `deployment/README.md` | 운영 배포 절차, 필요한 시크릿·환경변수, 서버 초기 설정 |
| `deployment/sql2widget.crudy.cloud.conf` | 운영 도메인용 Nginx reverse proxy 설정 |
| `.github/workflows/deploy.yml` | CI/CD — PR/main 테스트, GHCR 이미지 게시, VPS 배포, 실패 시 이전 이미지로 복구 |
| `scripts/deploy.sh` | VPS에서 `compose.production.yml`로 새 이미지를 pull·기동하는 배포 스크립트 (백엔드/프런트 이미지 태그를 인자로 받음) |

---

## 5. `docs/` — 문서 (본 폴더)

| 경로 | 역할 |
|------|------|
| `01-folder-structure.md` | 본 문서 |
| `features/*.md` | 기능별 상세 명세. `기능명세서.md`를 대체 완료 |
| `progress.md` | 작업 진행 상황. `현황.html`을 대체 완료 |
| `dashboard.html` | 전체 문서를 GitBook 스타일(좌측 목차 + 본문)로 묶은 HTML 문서 |
| `kanban.html` | 칸반형 정적 보드. `progress.md` + `features/*.md`를 시각화 |
| `PLAN.md`, `UI_BRIEF.md` | 초기 기획/비주얼 메모 (히스토리 참고용) |
| `design/README.md` | Figma/Stitch 익스포트 보관 안내 |

문서 전체 지도와 공통 규칙은 [AGENTS.md](../AGENTS.md)를 본다.

---

## 6. 기타

- `.agents/skills/` — 이 저장소에서 쓰는 코딩 에이전트 스킬 정의(`eli5`, `eli5-compress`). 앱 런타임과 무관.
- `.impeccable/design.json` — 디자인 토큰 원본 데이터로 추정(생성기 `impeccable` 산출물). `DESIGN.md` 프런트매터의 색상/타이포 값과 대응.
- `northwind_latest_5_all_columns.json` — 최상위에 있는 일회성 데이터 확인용 파일로 보임(스크립트 산출물 추정). 정식 산출물 경로가 아니므로 정리 대상 후보.
- `skills-lock.json` — 에이전트 스킬 버전 잠금 파일.

---

## 7. 관련 문서

→ [docs/features/](features/README.md): 기능 단위 상세 명세.
→ [docs/progress.md](progress.md): 작업 진행 상황.
→ [docs/dashboard.html](dashboard.html): 전체 문서를 GitBook 스타일로 묶은 HTML 문서.
→ [docs/kanban.html](kanban.html): 칸반형 정적 보드.
