# agent4any 기획서 (P0~P1)

## 1. 제품 한 줄

비기술 사용자가 자연어로 **SOC 보안 데이터**를 조회하고, 차트·리스트·표 위젯으로 결과를 확인한 뒤, **대화별 스테이지**에 드래그해 배치·자동 저장하는 에이전트 MVP.

## 2. 확정 결정

- Docker Compose가 로컬 개발 기준 경로
- 스테이지는 **대화마다 1개** (`conversation_id`)
- 스테이지 레이아웃: `react-grid-layout`
- LLM: 1차는 Mock only (SOC 시나리오 8종, 고객 DB SELECT 기반 props)
- 상태관리:
  1. fetch → `useSWR`
  2. 전역 UI 슬롯 → `useStore` (SWR 캐시 래퍼)
  3. Provider / `SWRConfig` **금지**
  4. 입력·드래그 중 → `useState`

## 3. 목표 / 비목표

### 목표 (P0~P1)

- Compose로 API·FE·서비스 DB·샘플 고객 DB 기동
- 로그인, 대화, Mock 채팅 Artifact
- 허용 컴포넌트 실렌더 (차트/리스트/표)
- 채팅 → 스테이지 DnD, 이동·리사이즈, 자동 저장·복원

### 비목표 (이후)

- 실 LLM, 실 RAG, 운영 배포 (P2~P6는 별도 로드맵)

## 4. 대표 시나리오 (SOC)

1. 지난달 공격당한 서버들의 공격 순위, 방법, 해결 방안을 보여줘.
2. 공격 유형별 비중을 보여줘.
3. SOC 보안 현황을 보고서 형태로 만들어줘.

추가 Mock: 심각도, 자산 위험도, 7일 추이, 취약점, 차단 IP, 인시던트.

## 5. 아키텍처

- Backend: Python FastAPI, `psycopg`, 순수 SQL (ORM 없음)
- Frontend: Vite React JavaScript (TypeScript 없음)
- DB: PostgreSQL 서비스 DB + **SOC 샘플 고객 DB**
- 고객 DB: 읽기 전용 `SELECT`만

## 6. 허용 컴포넌트

`KpiStat`, `DataTable`, `RankList`, `BarChart`, `LineChart`, `PieChart`, `MarkdownBlock`, `SourceList`, `FilterBar`, `KpiSparkline`, `PieTable`, `BarTable`

서버에서 화이트리스트 검증. 목록 밖 이름은 거부하거나 `DataTable` 폴백.

## 7. API 개요

```text
POST /api/auth/login
POST /api/auth/refresh
GET  /api/auth/me

POST /api/conversations
GET  /api/conversations
GET  /api/conversations/{id}
POST /api/chat

GET  /api/conversations/{id}/stage
PUT  /api/conversations/{id}/stage
POST /api/conversations/{id}/stage/widgets
PATCH /api/conversations/{id}/stage/widgets/{widget_id}
DELETE /api/conversations/{id}/stage/widgets/{widget_id}
```

## 8. 스테이지 모델

- 대화당 stage 1행
- 위젯: `layout { i, x, y, w, h }`, `component`, `title`, `props`, `source_widget_id`

## 9. 완료 기준 (1차)

- `docker compose up` 후 로그인 → 샘플 질문 3종 → 차트/리스트 표시
- 위젯을 스테이지로 드롭 → 배치·리사이즈 → 새로고침 후 유지
- Provider 패턴 없음

## 10. 로드맵 요약

| Phase | 내용 |
|-------|------|
| P0~P1 | Docker, Auth, Mock chat, Stage, 기본 UI |
| P2 | LLM provider + Mock 폴백 |
| P3 | 고객 DB 동적 라우팅 |
| P4 | DocumentProvider / RAG |
| P5 | 관리자 UI |
| P6 | 운영 배포 |

## 11. 고객 DB (SOC demo)

테이블: `servers`, `attack_events`, `incidents`, `vulnerability_findings`, `blocked_ips`

스키마 변경 후 기존 볼륨이 있으면:

```powershell
docker compose down -v
docker compose up --build
```
