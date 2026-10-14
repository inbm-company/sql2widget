# 작업 진행 상황

| 항목 | 내용 |
|------|------|
| 문서명 | 작업 진행 상황 |
| 기준일 | 2026-10-14 |
| 관련 문서 | [AGENTS.md](../AGENTS.md), [docs/features/](features/README.md), [PROJECT_HANDOFF.md](../PROJECT_HANDOFF.md) |

상태 라벨은 4종 고정: `완료` / `진행중` / `예정` / `보류`. 이 문서는 `docs/현황.html`(2026-09-03 스냅샷)을 대체한다 — 이전 스냅샷 수치는 6절에 남겨둔다.

---

## 1. 요약

- 로컬 데모 골격(로그인 → 질문 → 위젯 → Stage 핀 → 새로고침 유지)은 **완료**.
- 2026-09-03 스냅샷 이후 **프로젝트 계층**(대화 여러 개를 프로젝트 하나로 묶고, Stage를 프로젝트당 1개로)이 새로 들어왔다 — 당시 문서의 `/c/:id/view`는 지금 `/p/:projectId/view`로 바뀌었다.
- 실 LLM 경로(OpenAI-compatible + Gemini, 스키마 컨텍스트, 1회 복구 재시도)도 스냅샷 이후 상당히 진전됐다.
- 채팅 메시지 임베딩(pgvector 유사도 검색)은 이번 문서화 중 코드에서 새로 발견한 기능으로, 백엔드만 동작하고 프론트는 아직 안 붙었다.

---

## 2. 완료

| 항목 | 비고 |
|------|------|
| 설명 답변 본문 표시 — 테이블 구조·SOC 출처 설명의 MarkdownBlock 생성 제거 | 2026-10-14 전체 설명·테이블별 컬럼 표를 채팅 본문에 표시. 과거 채팅 설명 카드는 본문으로 표시하고 데이터 위젯·출처·기존 Stage 항목 유지. 관련 회귀 테스트 작성, 테스트·빌드·브라우저 검증은 사용자 승인 전 미실행. [chat.md](features/chat.md), [widgets-artifact.md](features/widgets-artifact.md) |
| 로그인/세션, JWT access+refresh, 역할 분리(admin/user/viewer)·로컬/운영 로그인 아이디 분리 | [auth.md](features/auth.md). 2026-10-06 운영 비밀번호 동기화 후 관리자·Viewer HTTPS 로그인/세션/프로젝트 조회 200, 로컬 로그인 유지 확인 |
| 프로젝트·대화 CRUD — 프로젝트 삭제·연관 데이터 정리·New chat 생성 오류 수정 | [projects-conversations.md](features/projects-conversations.md) |
| Artifact 위젯 렌더 + SQL 미리보기 · TanStack Charts와 분석 위젯 4종 추가 | 2026-10-13 누적 막대·히트맵·산점도·히스토그램 추가, 카탈로그 16개. SQL 변환·예상 질문·Stage 저장 경로 연결. Artifact JSON 전체 복사 버튼과 버튼 왼쪽 10px 성공·실패 안내 추가. 백엔드 전체 124개·프런트 14개 테스트·Vite 빌드 통과. 실제 Global Sales 데모 DB SELECT·Stage 추가/재조회·Viewer 4종 표시 확인. 실 LLM은 AI 키 미설정으로 미검증. [widgets-artifact.md](features/widgets-artifact.md) |
| 위젯 자체 데이터 조회 — 결과 비저장·원본 DB/SQL 정의 저장 | 2026-10-13 채팅·Stage·Viewer의 위젯별 GET·새로고침·로딩/오류 구현. 현재 소유자·tenant·역할 테이블 권한 검사, 기존 위젯 DB 정보 복원. 실제 Global Sales DB 7종 SELECT·임시 Stage 결과 비저장 검증, 브라우저 대역의 조회/새로고침/오류 복구/Viewer 확인. 전체 백엔드 169개 통과·기존 일반 대화 기대값 불일치 2개 실패, 프런트 23개·빌드 통과. 실 LLM·운영 배포는 미실행. [widgets-artifact.md](features/widgets-artifact.md) |
| Stage 드래그·이동·리사이즈·자동 저장·복원, 채팅과 Stage 너비 조절 | [stage.md](features/stage.md) |
| Viewer 읽기 전용 화면(`/p/:id/view`) | [viewer.md](features/viewer.md) |
| Admin 유지 + 별도 AI 설정·DB 관리 패널 — DB 연결 등록/테스트, 역할별 테이블 권한, 배경 클릭 닫기 | [admin.md](features/admin.md) |
| SOC + Global Sales 샘플 DB, 서비스 DB Docker Compose 구성 | `docker-compose.yml` |
| Northwind 로컬 시드, SKAX NMS 로컬·운영 스냅샷 복원·연결 등록 | `backend/scripts/seed_northwind_recent.py`, `seed_skax_nms.py` |
| 실 LLM 전용 채팅 에이전트(OpenAI-compatible, Gemini) — 스키마 컨텍스트 전달, 결과 기반 SQL 수정·위젯 재선택, 미완료 시 부분 결과·사유 반환(Mock 키워드 매칭 폴백은 2026-09-22 완전 삭제) | [chat.md](features/chat.md) |
| Provider별 AI 연결 설정·요청 분리, 로컬 OpenAI 호환 모델 지원(서버 모델 목록 select), Jev 공통 키 입력·저장 | 2026-10-13 관련 백엔드 80개·프런트 8개 테스트 및 Vite 빌드 통과. 실제 브라우저의 Jev 입력 마스킹·저장·Provider 전환·새로고침 복원을 확인하고 기존 설정을 복원. Jev API는 대역으로 검증, 실키 호출은 미실행. [admin.md](features/admin.md) |
| `llm_usage` 사용량 기록 골격(테이블 적재) | [admin.md](features/admin.md) 데이터 모델 |
| 문서 체계 정비 — `AGENTS.md`/`CLAUDE.md`, `docs/01-folder-structure.md`, `docs/features/*.md`, 본 문서, `docs/dashboard.html`, `docs/kanban.html` | 이번 문서화 작업 1~5번 전체 완료 |
| DB별 예상 질문 유사도 DB — 전체 테이블 질문 생성 → 유사 질문 참조 답변 생성 | [similarity-search-design.md](features/similarity-search-design.md) |
| 채팅 의도 라우팅 — Jev Choice(실패 시 2회 재시도 후 채팅 LLM 판단) → 데이터 조회 / 테이블 구조 답변 / 되묻기 선택지 | 단위 테스트와 실제 Jev 호출(2026-10-01, `jev-1.13.0`)로 확인 — Jev 경로·401 폴백·되묻기 모두 동작. `ROUTE_MIN_CONFIDENCE` 0.5는 아직 검증 전 초기값. [chat.md](features/chat.md) |
| 큰 DB의 SQL 계획 스키마 줄이기 — 허용 테이블 20개 초과 시 유사 질문이 쓴 테이블, 매칭이 없으면 전체 허용 스키마 전달, 실패 시 전체 스키마로 재시도 | 단위 테스트와 Northwind 실행(임계값 5로 낮춤)으로 확인. 100개 이상 DB(SKAX NMS)는 미검증. [chat.md](features/chat.md) |
| 채팅 처리 내역 표시·저장 — 선택 경로·분류 방식, SQL 테이블 선택·유사 질문 참조 | `messages.meta` 저장으로 새로고침 후 유지. 과거 답변은 기록 없음. [chat.md](features/chat.md) |
| 일반 대화 — 인사·잡담·일반 지식·개념 설명 | 2026-10-13 `general_chat` 경로·Jev/LLM 분류·세 경로 선택지·전체 본문 답변·처리 내역 표시 구현. 고객 DB 스키마 조회는 DB 경로에서만 수행. 사용자 요청에 따라 테스트·빌드·브라우저 검증 미실행. [chat.md](features/chat.md) |
| 에이전트 루프 및 위젯 선택·SQL 생성 분리 | 2026-10-13 SQL 데이터셋 생성·실행 후 실제 컬럼·타입·행 수로 복수 위젯 선택·개별 생성. 각 실제 호출 결과에서 다음 작업 결정, 같은 SQL의 여러 위젯 컬럼 연결·Stage 보존. 도구 호출 순서·SQL 수·생성 위젯 수·판단 호출·재계획 구분, 부분 결과·한도·반복 중단 구현. 테스트·검증용 빌드·브라우저 검증은 사용자 승인 전 미실행. [chat.md](features/chat.md) |
| 대화 문맥·후속 질문 처리 및 IME 조합 중 전송 방지 | 최근 20개 메시지 범위의 같은 DB 응답 이력을 라우터·SQL 계획·복구·구조 답변에 전달. 다른 DB·DB 정보 없는 과거 이력은 제외. 2026-10-13 관련 백엔드 테스트 70개, 프런트 테스트 4개, Vite 빌드 통과. 테스트 대역으로 검증했고 실모델·브라우저 IME·실 DB 재조회 검증은 미실행. [chat.md](features/chat.md) |
| 운영 배포 파이프라인 | 2026-10-01 Actions 테스트·GHCR 이미지 게시·VPS 실배포 성공 확인. SKAX 운영 DB 스냅샷 복원·연결·역할 권한 등록과 배포 후 읽기 전용 검사 포함. [deployment/README.md](../deployment/README.md) |
| DB/문서 프로젝트 분리 및 독립 실행 | sql2widget: DB 채팅·위젯 Stage, doc2graph: 문서 채팅·그래프. 동일 기본 UI, 독립 계정/설정/DB/볼륨, 기존 데이터 이전 없음. A 81/B 56 백엔드·A 4/B 15 프런트 테스트 및 빌드 통과. 교차 토큰 거부/기능 API 분리, SQL/Stage API·문서 업로드/적재/그래프 UI 확인. 2026-10-06 sql2widget 운영 전환 완료(6a88140): CI 테스트·이미지 게시·VPS 배포, HTTPS/API·기존 계정/프로젝트/대화 보존 확인. 실모델 유료 호출은 미실행 |

## 3. 진행중

| 항목 | 비고 |
|------|------|
| 채팅 메시지 임베딩·유사도 검색(pgvector, `chat_vector` DB) | 백엔드 저장·검색(`message_embeddings.py`)까지 완료, API가 `related_messages` 반환. **프론트 미표시** — `App.jsx`가 아직 렌더링 안 함 |
| 실 LLM 경로 하드닝 | 데이터 호출 루프·단계당 SQL 수정 5회·시간/호출 제한은 구현, 실모델 검증과 레이트리밋/서킷브레이커는 미완료. [PROJECT_HANDOFF.md](../PROJECT_HANDOFF.md) |

## 4. 예정

| 항목 | 우선순위 | 비고 |
|------|----------|------|
| 질문 유사도 테스트 하니스 — 비슷한 질문이 같은 furniture를 내는지 검증 | HIGH | [PROJECT_HANDOFF.md](../PROJECT_HANDOFF.md), 2026-09-03 스냅샷 #7과 동일 항목, 미착수 |
| Circle 게이지 조합 카탈로그 (ring × size × companion) | MED | 스냅샷 #9와 동일, `ALLOWED_COMPONENTS`에 아직 없음 |
| Viewer에 남은 다크 Orion 자리표시(CSS `variant="orion"`) 정리 | LOW | [DESIGN.md](../DESIGN.md)가 "정식 토큰 아님"으로 명시. [viewer.md](features/viewer.md) 참고 |
| 실 RAG(문서 검색) 고도화 — 현재 `DocumentProvider`는 Mock 고정 문서만 | LOW | 고정 SOC 데모 출처 보조 기능. 사용자 업로드 문서 그래프는 doc2graph 소유 |
| LLM 사용량(`llm_usage`) 조회 UI | 미지정 | 기록만 되고 화면에서 보여주지 않음. [admin.md](features/admin.md) |
| Stage 쓰기 API에 role 기반 서버측 검사 추가 여부 | 미지정 | 현재는 소유자 검사만 있고 `readOnly`는 프론트 전용. [stage.md](features/stage.md) 주의 항목 — 취약점이 아니라 설계 확인 필요 항목으로 분류 |

## 5. 보류 — 열려 있는 제품 결정

| 항목 | 비고 |
|------|------|
| 완성 Orion 대시보드 템플릿을 넣을지 | 스냅샷 #8과 동일. [PRODUCT.md](../PRODUCT.md) "Explicitly undecided"에 명시. **현재 기본 규칙은 "핀보드만, 템플릿 없음"**이며, 이 규칙을 바꾸려면 합의가 필요하다([AGENTS.md](../AGENTS.md) 제품 규칙 2) |

---

## 6. 히스토리 — 2026-09-03 스냅샷 (`docs/현황.html`, 대체됨)

당시 수치: 백로그 11건 중 완료 6 · 대기 5(55%). 완료 6건은 위 "2. 완료"에 모두 흡수됐다. 대기 5건(#7~#11)은 위 "4. 예정"과 "5. 보류"에 각각 대응한다 — 새로 생긴 항목(프로젝트 계층, 실 LLM 진전, 채팅 임베딩, 배포 파이프라인)은 스냅샷에는 없었다.

인수 시나리오(S-01~S-05)는 여전히 유효하며 기능 문서의 대표 시나리오로 이어졌다: SOC 유형별 비중 → PieTable → Stage 드래그([chat.md](features/chat.md), [stage.md](features/stage.md)), Global 지역 매출 → BarTable, viewer 제약([viewer.md](features/viewer.md)), 틀린 비밀번호 거부, 쓰기 SQL 차단([chat.md](features/chat.md) SQL 규칙).

---

## 7. 관련 문서

→ [docs/dashboard.html](dashboard.html): 전체 문서를 GitBook 스타일로 묶어 보여주는 HTML 문서.
→ [docs/kanban.html](kanban.html): `docs/features/*.md` + 본 문서를 시각화한 칸반형 정적 보드.
