# sql2widget 폴더 구조

| 항목 | 내용 |
|------|------|
| 문서명 | sql2widget 폴더 구조 |
| 기준일 | 2026-10-06 |
| 관련 문서 | [AGENTS](../AGENTS.md), [기능 색인](features/README.md) |

| 경로 | 역할 |
|------|------|
| `backend/app/main.py` | 이 앱의 인증·프로젝트·대화·채팅 API와 DB/Stage API |
| `backend/app/agent_service.py` | data_query/schema_qa 오케스트레이션 |
| `backend/app/` | DB SQL·예상 질문·위젯 Stage, 선택적 graph_backend, 공통 인증/LLM/Provider/표시용 처리 내역 |
| `backend/app/repositories/` | 프로젝트·대화와 앱 전용 데이터 접근, 순수 SQL |
| `backend/sql/migrations/` | 앱별 서비스 DB 스키마. 문서 그래프 테이블 제외 |
| `backend/scripts/` | 마이그레이션·독립 계정 초기화, 고객 DB/벡터 시드·스모크 |
| `backend/tests/test_seed_accounts.py` | 환경별 로그인 아이디 기본값·실 PostgreSQL 임시 테이블에서 계정 보존/충돌 검사 |
| `backend/tests/` | 앱별 기능·권한·독립성·토큰 격리 검증 |
| `frontend/src/App.jsx` | 같은 기본 로그인·사이드바·채팅·설정·분할 패널 UI |
| `frontend/src/StageCanvas.jsx` | 위젯 핀보드, 그래프 탭 없음 |
| `frontend/src/AdminPanel.jsx` | AI 설정과 DB 연결·권한·예상 질문 |
| `frontend/src/widgets/WidgetRenderer.jsx` | 차트·표·KPI 등 허용 위젯 |
| `frontend/src/api.js`, `aiSettings.js`, `store.js` | 앱별 토큰·AI 설정·API·SWR 키 |
| `frontend/src/styles.css`, `DESIGN.md` | 동일 기본 디자인에서 시작한 앱 스타일 |
| `frontend/tests/` | AI 설정 테스트 |
| `docker-compose.yml` | 새 독립 로컬 볼륨·포트, Neo4j 미필수 |
| `compose.production.yml` | 독립 운영 구성. 2026-10-06 sql2widget VPS 배포 확인 |
| `.github/workflows/` | 기존 SQL 테스트·이미지·배포 파이프라인의 기능 경계 갱신 |
| `docs/features/`, `docs/progress.md` | 구현 명세·현재 상태 |
| `docs/dashboard.html`, `docs/kanban.html` | 위 마크다운의 정적 스냅샷 |
| `docs/project-separation-proposal.md` | 합의된 범위·기능 소유권·구현 결과 |
