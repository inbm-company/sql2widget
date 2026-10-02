# agent4any / sql2widget — 에이전트용 프로젝트 문서

| 항목 | 내용 |
|------|------|
| 문서명 | 프로젝트 문서 (Claude / Codex 등 코딩 에이전트가 세션 시작 시 자동으로 읽는 문서) |
| 기준일 | 2026-10-02 |
| 대상 | 이 저장소에서 작업하는 AI 에이전트, 처음 들어오는 사람 |

이 문서는 저장소 전체 문서를 어디서 무엇을 보면 되는지 안내하고, 문서마다 반복 설명하지 않는 **공통 확정 규칙**과 **기능 개요**를 한 곳에 모은다. 여기 규칙이 다른 문서와 충돌하면 이 문서가 아니라 **구현 코드**가 기준이다.

---

## 1. 프로젝트 한 줄 설명

비기술 사용자가 자연어로 고객 DB(SOC 보안 / Global Sales)를 조회하고, 결과를 허용된 위젯(차트·표·KPI 등)으로 받은 뒤, **프로젝트마다 1개**인 Stage(핀보드)에 배치·저장하는 에이전트 MVP. 완성된 공유 대시보드 템플릿을 자동 생성하는 것은 목표가 아니다.

---

## 2. 주요 기능 개요

상세 스펙은 [docs/features/](docs/features/README.md)를 본다.

| 기능 | 한 줄 설명 | 상세 문서 |
|------|-----------|-----------|
| 로그인/세션 | 이메일·비밀번호 로그인, JWT access+refresh, `admin`/`viewer` 역할 구분 | [auth.md](docs/features/auth.md) |
| 프로젝트·대화 | 프로젝트(최상위 단위) 아래 여러 대화(conversation)를 생성·이름변경·삭제 | [projects-conversations.md](docs/features/projects-conversations.md) |
| 채팅(에이전트) | 자연어 질문 → 실 LLM(OpenAI-compatible/Gemini)이 SELECT 계획을 세워 실행 → 위젯 Artifact 반환. AI 키가 없거나 호출이 실패하면 추측하지 않고 에러를 그대로 반환 | [chat.md](docs/features/chat.md) |
| 채팅 의도 라우팅 | 질문을 데이터 조회 / 테이블 구조 답변 / 되묻기 선택지로 분류(TypeSafe Jev → 실패 시 채팅 LLM 판단). 확신이 낮으면 위젯 대신 선택지 버튼을 반환 | [chat.md](docs/features/chat.md) |
| 예상 질문 유사도 DB | 사용자 질문을 DB별로 검색하고 연결된 SQL·위젯 정보를 참조해 답변 생성, 관리자 전체 DB 예상 질문 생성 | [similarity-search-design.md](docs/features/similarity-search-design.md) |
| Artifact/위젯 표시 | 채팅 응답의 위젯을 미리보기·JSON 토글로 표시, 가능한 경우 실행된 SQL도 표시. 처리 내역에서 선택 경로·SQL 테이블 선택·유사 질문·복구 결과 확인(대화에 저장) | [widgets-artifact.md](docs/features/widgets-artifact.md) |
| Stage 배치 | 채팅 카드를 드래그하거나 버튼으로 프로젝트의 Stage(핀보드)에 추가, `react-grid-layout`으로 이동·리사이즈, 자동 저장·새로고침 후 복원 | [stage.md](docs/features/stage.md) |
| Viewer 전용 화면 | `/p/{projectId}/view` — 채팅·편집 없이 Stage만 읽기 전용으로 표시 | [viewer.md](docs/features/viewer.md) |
| 관리자 — DB 연결/권한/AI 설정 | 고객 PostgreSQL 연결 등록·테스트·테이블 권한, 브라우저별 AI 연결 설정 | [admin.md](docs/features/admin.md) |

데모 데이터셋은 두 개이며 동등하게 취급한다: `dbconn_demo`(SOC 보안 — 서버/공격/인시던트/취약점/차단IP), `dbconn_global`(Global Sales — 지역/제품/월별매출). 로컬 개발용으로 Northwind, SKAX NMS 샘플 DB도 함께 시드된다. SKAX NMS(`cinamon`, `dbconn_skax_nms`)는 운영에도 별도 DB·영속 볼륨으로 복원하고 연결·역할 권한을 자동 등록한다.

문서 업로드·엔티티 추출·문서 채팅·그래프 화면은 독립 `doc2graph`로 이동했다. 최소 그래프 기반은 `backend/app/graph_backend.py`에만 남겼으며 기본 미사용·UI 비표시다. 로컬 실행은 `.env.local`과 `sql2widget-local` Compose 이름으로 새 데이터를 사용한다. 토큰 issuer/브라우저 설정 키도 앱별로 분리했다.

---

## 3. 문서 지도

### 3.1 루트 문서

| 문서 | 역할 | 언제 보는가 |
|------|------|--------------|
| `AGENTS.md` / `CLAUDE.md` | 본 문서(공용). 문서 지도 + 공통 확정 규칙 + 기능 개요. Claude Code는 `CLAUDE.md`의 `@AGENTS.md` import로 자동 로드, Codex 등은 `AGENTS.md`를 직접 읽음 | 세션 시작 시 항상 |
| [README.md](README.md) | 로컬 실행 방법(Docker Compose), 상태관리 3원칙, LLM 환경변수, 스모크 테스트 명령 | 처음 로컬에 띄울 때 |
| [PRODUCT.md](PRODUCT.md) | 제품 정의, 사용자/역할, 성공 정의, 확정/미확정 제품 결정 | 기능을 추가하거나 범위를 판단할 때 |
| [DESIGN.md](DESIGN.md) | 디자인 시스템 — 색상, 타이포, 컴포넌트 스타일 토큰 | UI를 만들거나 스타일을 바꿀 때 |
| [PROJECT_HANDOFF.md](PROJECT_HANDOFF.md) | 대화 없이 저장소만 보고 이어받기 위한 요약 (현재 동작, 다음 작업 우선순위, 작업 시 주의) | 새 세션/새 작업자가 시작할 때 |

### 3.2 `docs/` 문서

| 문서 | 역할 | 상태 |
|------|------|------|
| [docs/01-folder-structure.md](docs/01-folder-structure.md) | 폴더·파일 단위 설명 | 완료 |
| [docs/project-separation-proposal.md](docs/project-separation-proposal.md) | DB 위젯 / 문서 지식그래프 기능 조사·분리안·사용자 결정 기록 | 구현 완료 — 로컬 독립 실행·테스트 검증, 운영 전환 미실행 |
| [docs/features/*.md](docs/features/README.md) | 기능별 상세 명세 (F-01 로그인처럼 기능 단위로 파일 분리) | 완료 — `docs/기능명세서.md` 대체함(삭제됨) |
| [docs/progress.md](docs/progress.md) | 작업 진행 상황 (완료/진행중/예정/보류) | 완료 — `docs/현황.html` 대체함(삭제됨) |
| [docs/dashboard.html](docs/dashboard.html) | `features/*.md` + `progress.md` 전체를 GitBook 스타일(좌측 목차 + 본문)로 묶어 보여주는 HTML 문서 | 완료 |
| [docs/kanban.html](docs/kanban.html) | `features/*.md` + `progress.md`를 시각화한 칸반형 정적 보드 | 완료 |
| [docs/PLAN.md](docs/PLAN.md) | 최초 기획서 (P0~P6 로드맵). 구현과 다르면 구현이 기준 | 유지 — 히스토리 참고용 |
| [docs/UI_BRIEF.md](docs/UI_BRIEF.md) | DESIGN.md 이전의 초기 비주얼 방향 메모 | 유지 — 히스토리 참고용 |
| [docs/design/README.md](docs/design/README.md) | Figma/Stitch 익스포트 보관 안내 | 유지 |

### 3.3 배포 문서

| 문서 | 역할 |
|------|------|
| [deployment/README.md](deployment/README.md) | 운영 배포 절차, 필요한 환경변수/시크릿, GitHub Actions 파이프라인 설명 |

### 3.4 읽는 순서 권장

1. 처음 온 경우: `README.md` (실행) → 본 문서 → [docs/01-folder-structure.md](docs/01-folder-structure.md) → `PRODUCT.md`
2. 특정 기능을 고치는 경우: [docs/features/](docs/features/README.md) 해당 기능 문서 → 관련 코드
3. 현재 뭐가 됐고 뭐가 남았는지 보는 경우: [docs/progress.md](docs/progress.md) 또는 [docs/kanban.html](docs/kanban.html)
4. 문서 전체를 훑어보는 경우: [docs/dashboard.html](docs/dashboard.html)
5. 세션을 새로 이어받는 경우: `PROJECT_HANDOFF.md`

### 3.5 문서 수정 시 동기화 절차

`docs/dashboard.html`/`docs/kanban.html`은 빌드 스크립트가 없다. **원본 마크다운을 손으로 복사해 넣은 정적 스냅샷**이라, 원본을 고쳐도 저절로 반영되지 않는다. 아래 관계를 지킨다.

| 원본(고치는 곳) | 반영해야 할 파생 문서 | 무엇을 맞추는가 |
|---|---|---|
| [docs/progress.md](docs/progress.md) 2~5절(완료/진행중/예정/보류) | [docs/kanban.html](docs/kanban.html) `<section class="board">` | 항목을 추가/이동/삭제하면 **같은 턴에** 해당 컬럼의 `.card`를 똑같이 추가/이동/삭제하고, `.col-head .count` 숫자를 실제 카드 개수와 일치시킨다. **칸반과 progress.md의 항목 수·내용이 어긋나면 안 된다** — 둘 중 하나만 고치고 끝내지 않는다. |
| [docs/progress.md](docs/progress.md) 전체 | [docs/dashboard.html](docs/dashboard.html) `<section id="progress">` | 요약 배지(`완료 14` 등 카운트), 완료/진행중 목록, 예정 표, 보류 문단을 progress.md와 동일하게 맞춘다. |
| `docs/features/*.md` 아무 파일 | [docs/dashboard.html](docs/dashboard.html)의 대응 `<section id="{파일명}">` | 그 섹션 본문을 원본 마크다운 내용과 맞춘다. **새 기능 문서를 추가했으면** 좌측 `<nav class="toc">`에 링크(`<a href="#id" data-id="id">`)도 추가한다. |
| `AGENTS.md` 4절(공통 확정 규칙) | [docs/dashboard.html](docs/dashboard.html) `<section id="overview">` | 규칙 문구가 달라지면 그대로 옮긴다(예: Mock 관련 규칙이 바뀌었는데 대시보드에 옛 문구가 남아있으면 안 됨). |
| `docs/features/README.md`의 표 | [docs/kanban.html](docs/kanban.html) "기능 문서" 섹션 | 새 문서가 추가되면 카드/행을 같이 추가한다. |

**순서**: 원본 마크다운을 먼저 고친다 → 영향받는 HTML 파일을 같은 작업 안에서 바로 고친다 → "나중에 한번에 재생성"으로 미루지 않는다(미루면 드리프트가 누적된다 — 실제로 2026-09-22 세션 중 `docs/progress.md`에 항목 하나를 추가하고 `kanban.html`/`dashboard.html`을 안 고쳐서 바로 어긋난 사례가 있었다).

---

## 4. 공통 확정 규칙

### 4.1 제품 규칙

1. **동등한 데모 두 세계** — SOC 보안(`dbconn_demo`)과 Global Sales(`dbconn_global`)는 하나가 메인이고 다른 하나가 곁다리인 관계가 아니다.
2. **핀보드지 포스터가 아니다** — 성공은 질문에 맞는 위젯이 채팅에 나오고 사용자가 몇 개를 Stage에 꽂는 것. 완성된 공유 대시보드 템플릿 자동 생성은 목표가 아니다.
3. **카탈로그 가구, 사용자 배치** — 에이전트는 후보 위젯을 제안하고, 배치는 사용자가 한다.
4. **닫힌 타입, 열린 값** — 차트 종류·레이아웃 문자열·색상(hex/CSS/HTML)을 에이전트가 지어내지 않는다. 데이터 값은 열려 있어도 컬럼 형태는 닫혀 있다.
5. **프로젝트 스코프** — Stage는 프로젝트당 1개. 전역 대시보드 라이브러리가 아니다.

### 4.2 기술/아키텍처 규칙

- 백엔드: Python, FastAPI, `psycopg`, 순수 SQL. **ORM 없음.**
- 프론트: Vite, React, **JavaScript**. **TypeScript 없음.**
- 상태관리 3원칙:
  1. 서버 fetch → `useSWR`
  2. 전역 UI 슬롯 → `useStore` (SWR 캐시 래퍼, Provider/`SWRConfig` 금지)
  3. 입력·드래그 중 즉시성이 필요한 로컬 상태 → `useState`
- 로컬 기동 기준: Docker Compose.
- Stage 레이아웃: `react-grid-layout`.
- 고객 DB는 **읽기 전용 `SELECT`만**. 앱이 DML을 실행하지 않는다.
- 위젯 컴포넌트 이름은 서버 화이트리스트(`ALLOWED_COMPONENTS`) 검증. 목록 밖 이름은 채팅에서는 `DataTable` 폴백, Stage 저장은 400으로 거부.
- 채팅 응답은 항상 실 LLM 호출로만 만든다(OpenAI-compatible). 키가 없거나 호출이 실패하면 **키워드 매칭 등으로 추측해서 대신 답하지 않고 에러를 그대로 반환**한다 — 에러를 성공한 것처럼 위장하지 않는다.
- 외부 문서 검색은 `DocumentProvider` 인터페이스로 추상화. 현재 구현은 Mock.
- 감사 로그에는 행위만 남긴다. 사용자 데이터를 수정하는 쿼리는 없다.

### 4.3 보안/운영 규칙

- 서비스 DB(`tenants`, `users`, `projects`, …)와 고객 DB(SOC/Global/Northwind 등)를 같은 커넥션·같은 쿼리 경로로 섞지 않는다.
- 모델이 서비스 DB에 임의 SQL을 실행하게 하지 않는다.
- 고객 DB 비밀번호·API 키를 로그에 남기지 않는다. `APP_SECRET`으로 암호화해 저장한다.
- 화이트리스트 밖 컴포넌트 이름을 새로 만들지 않는다.
- 근거 없는 해결 방안(보고서용 텍스트 등)을 지어내지 않는다.
- 합의 없이 DML, ORM, TypeScript, SWR Provider 패턴을 도입하지 않는다.
- 완성된 대시보드 템플릿을 기본 성공 조건으로 바꾸지 않는다.
- 운영 배포 시 개발용 기본 비밀번호를 쓰지 않는다 (`deployment/README.md` 참고).


### 4.4 문서 동기화 규칙

코드를 바꾸는 에이전트가 직접 문서를 갱신한다. "나중에 문서화"로 미루지 않고 **같은 작업 안에서** 끝낸다.

| 변경 | 같이 갱신할 문서 |
|------|------------------|
| 기능 동작·API·응답 형태 | `docs/features/*.md` 해당 문서와 그 문서의 기준일 |
| 파일·모듈 추가/삭제/역할 변경 | `docs/01-folder-structure.md` |
| 작업 상태 변화(완료/진행중/예정/보류) | `docs/progress.md` → `docs/kanban.html`·`docs/dashboard.html` (3.5절) |
| 환경변수 추가/변경 | `.env.example`, `README.md`, 운영에 필요하면 `deployment/README.md` |
| 새 세션이 알아야 할 동작·경로·주의사항 | `PROJECT_HANDOFF.md`, 본 문서 2절 기능 개요 표 |
| 본 문서 4절 규칙 문구 | `docs/dashboard.html` `<section id="overview">` (3.5절) |

작업 완료를 보고하기 전에 위 표로 누락을 점검한다. 갱신하지 않은 항목이 있으면 이유를 함께 적는다. 문서 작성 절차는 `docs-sync` 스킬을 따른다.

---

## 5. 문서 작성 컨벤션 (이번 문서화 작업 공통)

새로 만드는 `docs/01-folder-structure.md`, `docs/features/*.md`, `docs/progress.md`, `docs/dashboard.html`, `docs/kanban.html`에 공통 적용한다.

- 언어: 한국어. 코드 식별자·경로는 원문 그대로.
- 새 파일명은 영문 kebab-case (`01-folder-structure.md`, `features/chat.md`). 기존 한국어 파일명(`기능명세서.md` 등)은 대체되며 신규 명명 규칙을 따르지 않는다.
- 기능 문서는 `docs/기능명세서.md`의 관례를 유지: **기획이 아니라 현재 동작하는 구현이 기준.** 코드와 문서가 다르면 코드가 맞다.
- `docs/progress.md`의 상태 라벨은 4종으로 고정: `완료` / `진행중` / `예정` / `보류`.
- 각 문서 상단에 표로 문서명·기준일·관련 문서를 적는다 (본 문서와 동일한 형식).

---

## 6. 문서 세트 상태

1~5번 문서(본 문서, 폴더 구조, 기능별 문서, 진행 상황, `dashboard.html`+`kanban.html`) 모두 완료. 이후에는 코드가 바뀔 때마다 해당 기능 문서와 `docs/progress.md`를 갱신하고, `docs/dashboard.html`/`docs/kanban.html`은 그 내용을 반영해 다시 만든다.
