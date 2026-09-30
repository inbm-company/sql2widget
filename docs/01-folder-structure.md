# 폴더 구조 문서

| 항목 | 내용 |
|------|------|
| 문서명 | 폴더 구조 문서 |
| 기준일 | 2026-09-21 |
| 관련 문서 | [AGENTS.md](../AGENTS.md) / [CLAUDE.md](../CLAUDE.md)(공통 규칙), [docs/features/*.md](features)(기능별 상세, 작성 예정) |

이 문서는 저장소의 폴더·파일이 각각 무엇을 하는지 설명한다. 함수 단위 설명은 다루지 않는다 — 그건 `docs/features/*.md`(작성 예정)와 코드 자체가 기준이다. 포트 번호, 환경변수 값 같은 구체 수치는 `docker-compose.yml` / `.env.example`이 원본이며, 여기서는 파일이 하는 역할만 적는다.

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
| `main.py` | FastAPI 앱 엔트리포인트. 모든 `/api/*` 라우트 정의 (auth, projects, conversations, chat, database-connections, table-permissions, stage) |
| `config.py` | 환경변수 로드(`env()`), DB URL들, JWT 만료시간, `ALLOWED_COMPONENTS` 화이트리스트 정의 |
| `auth.py` | 비밀번호 해시(argon2), JWT access/refresh 발급·검증, `get_current_user` 의존성 |
| `contracts.py` | API 요청/응답 Pydantic 모델 (`LoginRequest`, `ChatRequest`, `StageWidgetIn` 등) |
| `db.py` | 서비스 DB 커넥션 컨텍스트매니저, `fetch_one`/`fetch_all`/`execute` 헬퍼 |
| `crypto.py` | `APP_SECRET` 기반 Fernet 암호화 — DB 연결 비밀번호 저장용 |
| `query.py` | 고객 DB용 읽기 전용 SQL 검증·실행. `SELECT`/`WITH` 외 차단, 허용 테이블 검사, 결과 JSON 직렬화 |
| `agent.py` | Mock 에이전트 — 키워드 매칭으로 SOC/Global 샘플 질문에 고정 Artifact 반환 |
| `agent_service.py` | Mock/실LLM 경로를 조율하는 오케스트레이터. `run_agent()`가 `main.py`의 `/api/chat`에서 호출됨 |
| `llm.py` | 실 LLM 클라이언트 (OpenAI-compatible + Gemini). 스키마를 프롬프트에 넣어 SELECT 플랜 JSON을 받아옴, 임베딩(`embed_text`) 포함 |
| `documents.py` | `DocumentProvider` 프로토콜 + Mock 구현. 해결 방안 텍스트에 쓰이는 문서 출처 검색 |

### 2.2 `backend/app/repositories/` — 순수 SQL 저장소 (ORM 없음)

| 파일 | 역할 |
|------|------|
| `projects.py` | `projects` 테이블 CRUD |
| `conversations.py` | `conversations` + `messages` CRUD, 제목 자동 갱신 |
| `stages.py` | `stages` + `stage_widgets` CRUD, 컴포넌트 화이트리스트 검증 |
| `connections.py` | `database_connections`(암호화 저장) + `table_permissions` CRUD, 연결 URL 조립 |
| `message_embeddings.py` | 채팅 메시지 임베딩 저장/유사도 검색 (pgvector, 별도 `chat_vector` DB) |

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
| `smoke_eval.py` | 로그인 + SOC 샘플 질문 스모크 (evals/questions.json과 별개의 빠른 점검) |
| `smoke_stage.py` | Stage 위젯 추가/조회 스모크 |

### 2.4 `backend/sql/` — DB별 SQL 원본

| 폴더 | 대상 DB | 내용 |
|------|---------|------|
| `migrations/` | 서비스 DB | `users`, `projects`, `conversations`, `stages`, `database_connections` 등 스키마 |
| `sample_customer/` | SOC 데모 DB (`dbconn_demo`) | `servers`, `attack_events`, `incidents`, `vulnerability_findings`, `blocked_ips` |
| `stage_global/` | Global Sales 데모 DB (`dbconn_global`) | `regions`, `products`, `monthly_sales` |
| `northwind/` | Northwind 샘플 DB | 표준 Northwind 스키마 + 최근 운영 데이터 델타 |
| `skax_nms/` | SKAX NMS 샘플 DB | 복원된 전체 덤프(`cinamon` 스키마), 로컬 설정 스크립트 |
| `chat_vector/` | 채팅 임베딩 DB | pgvector 확장, `message_embeddings` 테이블 |

### 2.5 나머지

- `backend/tests/` — pytest. `test_agent.py`(Mock 매칭), `test_conversations.py`, `test_projects.py`, `test_query.py`(SQL 검증), `test_llm_runtime.py`(LLM 경로), `test_schema_context.py`(권한 테이블 → LLM 스키마 컨텍스트).
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
| `App.jsx` | 워크스페이스 최상위 컴포넌트. 로그인, 사이드바, 채팅, 라우팅(`/`, `/p/:id/view`)을 모두 포함하는 가장 큰 파일 (803줄) |
| `StageCanvas.jsx` | Stage 핀보드. `react-grid-layout` 기반 드래그·리사이즈·자동 저장, `addWidgetToStage` export |
| `ViewerStagePage.jsx` | `/p/:projectId/view` 라우트. `StageCanvas`를 읽기 전용으로 감싸는 얇은 래퍼 |
| `AdminPanel.jsx` | 관리자 드로어 — DB 연결 등록/테스트, AI 설정, 테이블 권한 |
| `widgets/WidgetRenderer.jsx` | 위젯 컴포넌트 렌더러. `component` 이름별로 Recharts 차트/표/KPI 등을 그림 |
| `sqlHelpers.js` | 어떤 컴포넌트가 SQL 보기를 지원하는지(`canShowSql`), 위젯에서 실행 SQL을 뽑는 로직(`resolveWidgetSql`) |
| `store.js` | 상태관리 3원칙의 구현부. `useStore`(SWR 캐시 기반 전역 슬롯), `storeKeys`(SWR 키 레지스트리) |
| `api.js` | 백엔드 API 클라이언트. 토큰 저장/갱신(`localStorage`), AI 설정 저장, 401 시 refresh 재시도 |
| `constants.js` | 데이터셋별 샘플 질문 목록 (SOC/Global/Northwind) |
| `styles.css` | 전역 스타일. 토큰은 `DESIGN.md` 기준 |

---

## 4. 배포 / 인프라

| 경로 | 역할 |
|------|------|
| `docker-compose.yml` | 로컬 개발 스택 (frontend, backend, 서비스 DB, 샘플 고객 DB들) |
| `compose.production.yml` | 운영 스택. DB/API는 외부 포트를 열지 않고 프런트만 리버스 프록시로 노출 |
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
