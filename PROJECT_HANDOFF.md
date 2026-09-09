# agent4any / sql2widget 인수인계

이 문서는 대화 없이 저장소만 보고 이어가기 위한 기준이다.

새 작업에서는 이렇게 요청한다.

```text
PROJECT_HANDOFF.md와 저장소를 먼저 확인하고, 기존 설계 결정을 유지하면서
미완료 작업 중 우선순위가 가장 높은 항목부터 계속 구현해줘.
```

현황 한 장: `docs/현황.html` (2026-09-03 스냅샷).  
기능 명세: `docs/기능명세서.md` (구현 기준).  
제품 규칙: `PRODUCT.md`. 시각: `DESIGN.md`.

---

## 1. 제품

비기술 사용자가 자연어로 고객 DB를 조회하고, 허용된 위젯으로 받은 뒤, **대화마다 1개**인 Stage에 핀한다.

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
- 스테이지는 대화마다 1개. 레이아웃은 `react-grid-layout`.
- 고객 DB는 읽기 전용 `SELECT`만.
- 위젯 이름은 서버 화이트리스트. 모르는 키/차트 타입은 버린다.
- LLM 기본은 Mock. 실모델은 OpenAI-compatible. 키 없거나 실패하면 Mock 폴백.
- 외부 문서는 `DocumentProvider`. 현재는 Mock.
- 감사 로그에는 행위만 남긴다. 사용자 데이터 수정 쿼리 없음.

---

## 3. 지금 동작하는 것

- 로그인 JWT (access + refresh). admin / viewer.
- 대화 CRUD, Mock 채팅 Artifact, 샘플 질문.
- Recharts 위젯 렌더 (KPI, 표, 순위, 막대/선/파이, PieTable, BarTable 등).
- Stage 드래그·이동·리사이즈·자동 저장·복원.
- Admin: 연결 등록·테스트, 역할별 테이블 권한.
- Viewer: 채팅·DnD 없음. `/c/:id/view` 읽기 전용.
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
backend/app/agent.py                Mock 매칭
backend/app/agent_service.py        LLM/Mock 실행 경로
backend/app/llm.py                  실모델 클라이언트
backend/app/query.py                SQL 검증, 읽기 전용 실행
backend/app/contracts.py            위젯 계약
backend/app/documents.py            Mock 문서
backend/app/repositories/           순수 SQL 저장소
backend/sql/migrations/             서비스 DB
backend/sql/sample_customer/        SOC 샘플
backend/sql/stage_global/           Global Sales 샘플
frontend/src/App.jsx                워크스페이스
frontend/src/StageCanvas.jsx        Stage
frontend/src/widgets/WidgetRenderer.jsx
frontend/src/store.js               SWR 래퍼
docker-compose.yml                  로컬 스택
docs/기능명세서.md
docs/현황.html
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
GET/POST /api/conversations
GET/PATCH/DELETE /api/conversations/{id}
POST /api/chat
GET/PUT /api/conversations/{id}/stage
POST /api/conversations/{id}/stage/widgets
PATCH/DELETE /api/conversations/{id}/stage/widgets/{widget_id}
GET/POST /api/database-connections
POST /api/database-connections/{id}/test
GET  /api/database-connections/{id}/tables
POST /api/database-connections/{id}/preview-sql   (admin)
GET/PUT /api/table-permissions
GET  /api/health
```

---

## 7. 다음 작업

우선순위는 아래 순이다. 이미 된 Admin/Viewer/Stage/연결 라우팅을 다시 만들지 않는다.

1. 질문 유사도 테스트 하니스 — 비슷한 질문이 같은 furniture를 내는지.
2. 제품 결정 — Orion 포스터 템플릿을 넣을지. 현재 규칙: 핀보드만.
3. Circle 게이지 조합 카탈로그 (ring × size × companion).
4. Viewer에 남은 다크 Orion 자리표시 정리.
5. P2 실 LLM + Mock 폴백 hardening.
6. 실 RAG, 운영 배포 (HTTPS, 백업, 강한 `APP_SECRET`, 데모 계정 제거).

---

## 8. 작업 시 주의

- 서비스 DB와 고객 DB를 섞지 않는다.
- 모델이 서비스 DB에 임의 SQL을 실행하게 하지 않는다.
- 고객 DB 비밀번호·API 키를 로그에 남기지 않는다.
- 허용 목록 밖 컴포넌트 이름을 만들지 않는다.
- 근거 없는 해결 방안을 지어내지 않는다.
- 합의 없이 DML, ORM, TypeScript, SWR Provider를 넣지 않는다.
- 완성 대시보드 템플릿을 기본 성공 조건으로 바꾸지 않는다.
