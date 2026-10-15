# sql2widget 폴더 구조

| 항목 | 내용 |
|------|------|
| 문서명 | sql2widget 폴더 구조 |
| 기준일 | 2026-10-15 |
| 관련 문서 | [AGENTS](../AGENTS.md), [기능 색인](features/README.md) |

| 경로 | 역할 |
|------|------|
| `backend/app/providers/together.py`, `backend/tests/test_together_provider.py` | Together OpenAI 호환 어댑터·임베딩 제약, 공급자/URL별 키 격리·JSON 요청·전용 임베딩 차원 회귀 검사 |
| `backend/app/main.py` | 이 앱의 인증·프로젝트·대화·채팅 API와 DB/Stage API |
| `backend/tests/test_question_plan.py`, `frontend/tests/chatTrace.test.js` | 하위 질문 조건 보존·누락 거부, 경로 순서/반복과 재계획 질문 표시 회귀 검사 |
| `backend/tests/test_question_steps.py` | 여러 질문 실행·동일 경로 복귀·부분 실패·되묻기·재계획 질문 연결 검사(모델/DB 대역) |
| `backend/app/chat_cancellation.py` | 채팅 연결 종료 감지·요청별 취소 신호·동기 작업 경계 확인 |
| `backend/app/agent_service.py` | 계획·단계별 분류/실행·평가·재계획 루프와 결과 병합, data_query/schema_qa/general_chat 실행 |
| `backend/app/agent_plan.py` | 원래 요청의 단계 계획·목표 평가·재계획 결정, 모델 시간 예산과 루프 상한 |
| `backend/app/data_plan.py` | 독립 SQL 데이터셋 생성과 실행 결과 기반 복수 위젯 선택의 별도 모델 호출·검증 |
| `backend/app/data_agent.py` | 실제 데이터 도구 호출마다 상태 갱신·다음 작업 결정, SQL 실행·수정·복수 위젯 개별 생성·부분 결과 보존 |
| `backend/app/widget_bindings.py` | 실행 결과 컬럼을 위젯 역할에 연결·검증, 조회 시 역할별 데이터 변환 |
| `backend/app/widget_queries.py` | 데이터 없는 위젯 정의 정규화·Stage 저장, 현재 권한으로 SQL 조회 |
| `backend/app/widget_props.py` | 모든 SQL 위젯의 실행 시점 props 변환, 분석 4종의 별칭·수치 검증 |
| `backend/app/chat_flow.py` | 현재 대화의 같은 DB 응답 이력·직전 경로·위젯 SQL/본문을 후속 질문 문맥으로 구성 |
| `backend/app/` | DB SQL·예상 질문·위젯 Stage, 선택적 graph_backend, 공통 인증/LLM/Provider/표시용 처리 내역 |
| `backend/app/repositories/` | 프로젝트·대화와 앱 전용 데이터 접근, 순수 SQL |
| `backend/sql/migrations/` | 앱별 서비스 DB 스키마. 문서 그래프 테이블 제외 |
| `backend/scripts/` | 마이그레이션·독립 계정 초기화, 고객 DB/벡터 시드·스모크 |
| `backend/tests/test_seed_accounts.py` | 환경별 로그인 아이디 기본값·실 PostgreSQL 임시 테이블에서 계정 보존/충돌 검사 |
| `backend/tests/test_chat_flow.py` | 대화·DB 문맥 범위, API·라우터·SQL 계획·복구·구조 답변의 문맥 전달 검증 |
| `backend/tests/test_jev_chat_api.py` | 채팅 요청 Jev 키 우선순위·형식 검사·모델 입력 및 응답/저장 데이터 비노출 검증 |
| `backend/tests/test_widget_queries.py`, `test_widget_queries_live.py` | 데이터 비저장·조회 권한·기존 정의 호환·실 고객 DB SELECT와 임시 Stage 저장 검증 |
| `backend/tests/test_widget_props.py` | 신규 분석 위젯의 SQL 변환·빈 결과·잘못된 구간·Artifact/Stage JSON 경로 검증 |
| `backend/tests/` | 앱별 기능·권한·독립성·토큰 격리 검증 |
| `frontend/src/App.jsx` | 같은 기본 로그인·사이드바·채팅·설정·분할 패널 UI |
| `frontend/src/chatMessages.js`, `frontend/tests/chatMessages.test.js` | 서버 조회와 임시 질문의 중복 표시 방지, 과거 동일 질문·대화 범위 회귀 테스트 |
| `frontend/src/ChatText.jsx`, `chatText.js` | 설명 본문의 제목·목록·코드·표 표시, 과거 MarkdownBlock 채팅 카드를 본문으로 표시 |
| `backend/tests/test_chat_text.py`, `frontend/tests/chatText.test.js` | 구조 답변 본문·오류·조회 위젯/출처 보존, 과거 설명 카드·본문 표/코드 호환 검증 |
| `frontend/src/StageCanvas.jsx` | 위젯 핀보드, 그래프 탭 없음 |
| `frontend/src/AdminPanel.jsx` | AI 설정과 DB 연결·권한·예상 질문 |
| `frontend/src/widgets/QueryWidget.jsx`, `widgetData.js` | 채팅·Stage·Viewer의 SWR 데이터 조회·새로고침·로딩/오류와 데이터 없는 복사 정의 |
| `frontend/src/widgets/WidgetRenderer.jsx` | 허용 위젯. BarChart와 신규 분석 4종은 TanStack Charts, 나머지 차트는 Recharts |
| `frontend/src/widgets/tanstackBarChart.js` | 기존 BarChart props를 고정된 TanStack 막대 차트 정의로 변환 |
| `frontend/src/widgets/tanstackAnalyticalCharts.js` | 누적 막대·히트맵·산점도·히스토그램의 고정된 TanStack 정의·범례·툴팁 |
| `frontend/src/api.js`, `aiSettings.js`, `store.js` | 앱별 토큰·AI 설정·API·SWR 키 |
| `frontend/tests/widgetData.test.js` | 복사 시 조회 데이터 제외·원본 DB 유지·위젯별 조회 URL 검증 |
| `frontend/tests/apiAiHeaders.test.js` | Jev 공통 키의 채팅 전용 헤더 전달과 키 삭제 후 전달 중단 검증 |
| `frontend/src/styles.css`, `DESIGN.md` | 동일 기본 디자인에서 시작한 앱 스타일 |
| `frontend/tests/` | AI 설정·TanStack 차트의 데이터/구간/크기/라벨 이스케이프·카탈로그 일치 테스트 |
| `docker-compose.yml` | 새 독립 로컬 볼륨·포트, Neo4j 미필수 |
| `frontend/vite.config.js` | 로컬 Vite의 /kanban·/docs HTML 제공, 이전 주소 301 연결과 API 프록시 |
| `frontend/deployment/nginx.conf` | 운영 `/kanban`·`/docs` HTML 제공, 이전 주소 301 연결과 API 프록시 |
| `compose.production.yml` | 칸반·대시보드 공개용 `public-docs/` 읽기 전용 마운트. 독립 운영 구성. 2026-10-06 sql2widget VPS 배포 확인 |
| `.github/workflows/` | 기존 SQL 테스트·이미지·배포 파이프라인의 기능 경계 갱신 |
| `docs/features/`, `docs/progress.md` | 구현 명세·현재 상태 |
| `docs/dashboard.html`, `docs/kanban.html` | `scripts/render_docs.py`가 위 마크다운에서 생성한 HTML. 직접 수정하지 않음 |
| `docs/templates/` | 두 HTML의 틀(스타일·영역 필터 스크립트) |
| `scripts/test_render_docs.py` | 작업 ID·제목/상세 연결·중복/누락 거부·카드 템플릿 연결의 생성기 회귀 테스트 |
| `docs/temp/` | 보관 기록. 진행도 이전 형식의 히스토리(`progress-history-2026-10-14.md`) |
| `scripts/render_docs.py` | 마크다운에서 두 HTML 생성·제목 앵커와 웹 문서 링크 지정, `--check`로 동기화 검사. 외부 의존성 없음 |
| `docs/project-separation-proposal.md` | 합의된 범위·기능 소유권·구현 결과 |
