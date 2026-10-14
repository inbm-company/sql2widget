# 진행도 이전 기록 (2026-10-14 보관)

기준일: 2026-10-14. 진행도를 기능 영역별 형식으로 바꾸면서 기존 `docs/progress.md` 6절(히스토리)을 그대로 옮겼다. 당시 수치·검증 상태를 보존한 기록이며 현재 상태는 [진행도](../progress.md)를 따른다.

## 2026-09-03 스냅샷과 인수 시나리오

당시 수치: 백로그 11건 중 완료 6 · 대기 5(55%). 당시 완료 기능은 현재 기능별 완료 목록과 상세 기능 문서로 이어진다. 2026-10-14 사용자 결정으로 Orion 대시보드 템플릿·Circle 게이지·실 RAG 고도화·LLM 사용량 조회 UI를 현재 계획에서 제외했다. 당시 대기 항목 중 질문 표현별 결과 평가(#7)는 현재 계획의 예상 질문 검증에 포함했다. 새로 생긴 항목(프로젝트 계층, 실 LLM 진전, 채팅 임베딩, 배포 파이프라인)은 스냅샷에는 없었다.

인수 시나리오(S-01~S-05)는 여전히 유효하며 기능 문서의 대표 시나리오로 이어졌다: SOC 유형별 비중 → PieTable → Stage 드래그([chat.md](../features/chat.md), [stage.md](../features/stage.md)), Global 지역 매출 → BarTable, viewer 제약([viewer.md](../features/viewer.md)), 틀린 비밀번호 거부, 쓰기 SQL 차단([chat.md](../features/chat.md) SQL 규칙).



## 기능별로 묶기 전의 수정·운영 이력

아래는 2026-10-14 기능별 정리 이전 기록이다. 당시 수치·카탈로그 개수·검증 상태를 보존한 이력이며 현재 상태는 [진행도](../progress.md)와 상세 명세를 따른다.

| 항목 | 비고 |
|------|------|
| 응답 대기 중 사용자 질문 중복 표시 수정 | 2026-10-14 SWR 재조회에서 이번 질문이 확인되면 임시 말풍선만 숨김. 과거 동일 질문은 유지하고 임시 질문·대기 표시는 해당 대화로 제한. 회귀 테스트 작성, 테스트·빌드·브라우저 검증은 사용자 승인 전 미실행. [chat.md](../features/chat.md) |
| 설명 답변 본문 표시 — 테이블 구조·SOC 출처 설명의 MarkdownBlock 생성 제거 | 2026-10-14 전체 설명·테이블별 컬럼 표를 채팅 본문에 표시. 과거 채팅 설명 카드는 본문으로 표시하고 데이터 위젯·출처·기존 Stage 항목 유지. 관련 회귀 테스트 작성, 테스트·빌드·브라우저 검증은 사용자 승인 전 미실행. [chat.md](../features/chat.md), [widgets-artifact.md](../features/widgets-artifact.md) |
| 로그인/세션, JWT access+refresh, 역할 분리(admin/user/viewer)·로컬/운영 로그인 아이디 분리 | [auth.md](../features/auth.md). 2026-10-06 운영 비밀번호 동기화 후 관리자·Viewer HTTPS 로그인/세션/프로젝트 조회 200, 로컬 로그인 유지 확인 |
| 프로젝트·대화 CRUD — 프로젝트 삭제·연관 데이터 정리·New chat 생성 오류 수정 | [projects-conversations.md](../features/projects-conversations.md) |
| Artifact 위젯 렌더 + SQL 미리보기 · TanStack Charts와 분석 위젯 4종 추가 | 2026-10-13 누적 막대·히트맵·산점도·히스토그램 추가, 카탈로그 16개. SQL 변환·예상 질문·Stage 저장 경로 연결. Artifact JSON 전체 복사 버튼과 버튼 왼쪽 10px 성공·실패 안내 추가. 백엔드 전체 124개·프런트 14개 테스트·Vite 빌드 통과. 실제 Global Sales 데모 DB SELECT·Stage 추가/재조회·Viewer 4종 표시 확인. 실 LLM은 AI 키 미설정으로 미검증. [widgets-artifact.md](../features/widgets-artifact.md) 2026-10-14 채팅 프리뷰를 제목 포함 320px로 고정하고 내용·SQL 패널이 남은 공간을 채우도록 수정. 이번 높이 변경의 테스트·빌드·브라우저 검증은 사용자 승인 전 미실행. |
| 위젯 자체 데이터 조회 — 결과 비저장·원본 DB/SQL 정의 저장 | 2026-10-13 채팅·Stage·Viewer의 위젯별 GET·새로고침·로딩/오류 구현. 현재 소유자·tenant·역할 테이블 권한 검사, 기존 위젯 DB 정보 복원. 실제 Global Sales DB 7종 SELECT·임시 Stage 결과 비저장 검증, 브라우저 대역의 조회/새로고침/오류 복구/Viewer 확인. 전체 백엔드 169개 통과·기존 일반 대화 기대값 불일치 2개 실패, 프런트 23개·빌드 통과. 실 LLM·운영 배포는 미실행. [widgets-artifact.md](../features/widgets-artifact.md) |
| Stage 드래그·이동·리사이즈·자동 저장·복원, 채팅과 Stage 너비 조절 | [stage.md](../features/stage.md) |
| Viewer 읽기 전용 화면(`/p/:id/view`) | [viewer.md](../features/viewer.md) |
| Admin 유지 + 별도 AI 설정·DB 관리 패널 — DB 연결 등록/테스트, 역할별 테이블 권한, 배경 클릭 닫기 | [admin.md](../features/admin.md) |
| SOC + Global Sales 샘플 DB, 서비스 DB Docker Compose 구성 | `docker-compose.yml` |
| Northwind 로컬 시드, SKAX NMS 로컬·운영 스냅샷 복원·연결 등록 | `backend/scripts/seed_northwind_recent.py`, `seed_skax_nms.py` |
| 실 LLM 전용 채팅 에이전트(OpenAI-compatible, Gemini) — 스키마 컨텍스트 전달, 결과 기반 SQL 수정·위젯 재선택, 미완료 시 부분 결과·사유 반환(Mock 키워드 매칭 폴백은 2026-09-22 완전 삭제) | [chat.md](../features/chat.md) |
| Provider별 AI 연결 설정·요청 분리, 로컬 OpenAI 호환 모델 지원(서버 모델 목록 select), Jev 공통 키 입력·저장 | 2026-10-13 관련 백엔드 80개·프런트 8개 테스트 및 Vite 빌드 통과. 실제 브라우저의 Jev 입력 마스킹·저장·Provider 전환·새로고침 복원을 확인하고 기존 설정을 복원. Jev API는 대역으로 검증, 실키 호출은 미실행. [admin.md](../features/admin.md) 2026-10-14 Gemini 기본값만 3.8 Flash로 변경. 저장된 3.6 모델·키·다른 Provider·사용자 지정 다른 모델은 유지하며 기존 2.5 모델 전환 규칙 보존. 이번 모델 변경의 테스트·실모델 호출·빌드·브라우저 검증은 승인 전 미실행. |
| `llm_usage` 사용량 기록 골격(테이블 적재) | [admin.md](../features/admin.md) 데이터 모델 |
| 문서 체계 정비 — `AGENTS.md`/`CLAUDE.md`, `docs/01-folder-structure.md`, `docs/features/*.md`, 본 문서, `docs/dashboard.html`, `docs/kanban.html` | 이번 문서화 작업 1~5번 전체 완료 |
| DB별 예상 질문 유사도 DB — 전체 테이블 질문 생성 → 유사 질문 참조 답변 생성 | [similarity-search-design.md](../features/similarity-search-design.md) |
| 채팅 의도 라우팅 — Jev Choice(실패 시 2회 재시도 후 채팅 LLM 판단) → 데이터 조회 / 테이블 구조 답변 / 되묻기 선택지 | 단위 테스트와 실제 Jev 호출(2026-10-01, `jev-1.13.0`)로 확인 — Jev 경로·401 폴백·되묻기 모두 동작. `ROUTE_MIN_CONFIDENCE` 0.5는 아직 검증 전 초기값. [chat.md](../features/chat.md) |
| 큰 DB의 SQL 계획 스키마 줄이기 — 허용 테이블 20개 초과 시 유사 질문이 쓴 테이블, 매칭이 없으면 전체 허용 스키마 전달, 실패 시 전체 스키마로 재시도 | 단위 테스트와 Northwind 실행(임계값 5로 낮춤)으로 확인. 100개 이상 DB(SKAX NMS)는 미검증. [chat.md](../features/chat.md) |
| 채팅 처리 내역 표시·저장 — 선택 경로·분류 방식, SQL 테이블 선택·유사 질문 참조 | `messages.meta` 저장으로 새로고침 후 유지. 과거 답변은 기록 없음. [chat.md](../features/chat.md) |
| 일반 대화 — 인사·잡담·일반 지식·개념 설명 | 2026-10-13 `general_chat` 경로·Jev/LLM 분류·세 경로 선택지·전체 본문 답변·처리 내역 표시 구현. 고객 DB 스키마 조회는 DB 경로에서만 수행. 사용자 요청에 따라 테스트·빌드·브라우저 검증 미실행. [chat.md](../features/chat.md) |
| 에이전트 루프 및 위젯 선택·SQL 생성 분리 | 2026-10-13 SQL 데이터셋 생성·실행 후 실제 컬럼·타입·행 수로 복수 위젯 선택·개별 생성. 각 실제 호출 결과에서 다음 작업 결정, 같은 SQL의 여러 위젯 컬럼 연결·Stage 보존. 도구 호출 순서·SQL 수·생성 위젯 수·판단 호출·재계획 구분, 부분 결과·한도·반복 중단 구현. 테스트·검증용 빌드·브라우저 검증은 사용자 승인 전 미실행. [chat.md](../features/chat.md) |
| 대화 문맥·후속 질문 처리 및 IME 조합 중 전송 방지 | 최근 20개 메시지 범위의 같은 DB 응답 이력을 라우터·SQL 계획·복구·구조 답변에 전달. 다른 DB·DB 정보 없는 과거 이력은 제외. 2026-10-13 관련 백엔드 테스트 70개, 프런트 테스트 4개, Vite 빌드 통과. 테스트 대역으로 검증했고 실모델·브라우저 IME·실 DB 재조회 검증은 미실행. [chat.md](../features/chat.md) |
| 운영 배포 파이프라인 | 2026-10-01 Actions 테스트·GHCR 이미지 게시·VPS 실배포 성공 확인. SKAX 운영 DB 스냅샷 복원·연결·역할 권한 등록과 배포 후 읽기 전용 검사 포함. [deployment/README.md](../../deployment/README.md) 2026-10-14 칸반·문서 대시보드 HTML을 운영 `/docs/kanban.html`·`/docs/dashboard.html`에 공개. 기존 앱 이미지로 프런트만 재생성했고 백엔드·DB·계정은 변경하지 않음. 공개 URL 응답·업로드 파일 일치 검사는 사용자 승인 전 미실행. 2026-10-14 로컬·원격 main의 분기된 기록을 병합해 기존 앱 변경과 HTML 공개 설정을 함께 푸시. 최초 최신 코드 CI는 백엔드 80개 통과·3개 실패(현행 계획·평가·데이터 실행 구조와 맞지 않는 테스트 대역). 세 테스트의 대역을 현재 호출 구조로 갱신했으며 수정 후 결과는 GitHub Actions의 최신 실행을 확인한다. 2026-10-14 사용자 승인으로 운영 칸반 주소를 `/kanban`, 문서 대시보드 주소를 `/docs`로 변경. 기존 `/docs/kanban.html`·`/docs/dashboard.html` 및 끝 슬래시 주소는 새 주소로 301 연결. 푸시 후 별도 테스트·빌드·브라우저·접속 검증은 사용자 요청으로 실행하지 않는다. 2026-10-14 로컬 Vite에도 /kanban·/docs와 이전 주소 301 연결 추가. 로컬 Compose가 docs/를 읽기 전용으로 마운트하며 직접 npm run dev 실행도 같은 HTML을 제공한다. 테스트·빌드·브라우저 접속 검증은 사용자 요청으로 미실행. |
| DB/문서 프로젝트 분리 및 독립 실행 | sql2widget: DB 채팅·위젯 Stage, doc2graph: 문서 채팅·그래프. 동일 기본 UI, 독립 계정/설정/DB/볼륨, 기존 데이터 이전 없음. A 81/B 56 백엔드·A 4/B 15 프런트 테스트 및 빌드 통과. 교차 토큰 거부/기능 API 분리, SQL/Stage API·문서 업로드/적재/그래프 UI 확인. 2026-10-06 sql2widget 운영 전환 완료(6a88140): CI 테스트·이미지 게시·VPS 배포, HTTPS/API·기존 계정/프로젝트/대화 보존 확인. 실모델 유료 호출은 미실행 |
