# 작업 진행 상황

| 항목 | 내용 |
|------|------|
| 문서명 | 작업 진행 상황 |
| 기준일 | 2026-09-30 |
| 관련 문서 | [AGENTS.md](../AGENTS.md), [docs/features/](features/README.md), [PROJECT_HANDOFF.md](../PROJECT_HANDOFF.md) |

상태 라벨은 4종 고정: `완료` / `진행중` / `예정` / `보류`. 이 문서는 `docs/현황.html`(2026-09-03 스냅샷)을 대체한다 — 이전 스냅샷 수치는 6절에 남겨둔다.

---

## 1. 요약

- 로컬 데모 골격(로그인 → 질문 → 위젯 → Stage 핀 → 새로고침 유지)은 **완료**.
- 2026-09-03 스냅샷 이후 **프로젝트 계층**(대화 여러 개를 프로젝트 하나로 묶고, Stage를 프로젝트당 1개로)이 새로 들어왔다 — 당시 문서의 `/c/:id/view`는 지금 `/p/:projectId/view`로 바뀌었다.
- 실 LLM 경로(OpenAI-compatible + Gemini, 스키마 컨텍스트, 1회 복구 재시도)도 스냅샷 이후 상당히 진전됐다.
- 채팅 메시지 임베딩(pgvector 유사도 검색)은 이번 문서화 중 코드에서 새로 발견한 기능으로, 백엔드만 동작하고 프론트는 아직 안 붙었다.
- Graph RAG 준비용 Neo4j 로컬 설치와 문서 경로 등록·수동 적재는 **완료**. 문서 본문과 명시된 문서 링크를 저장하며, 질문에서 검색하는 연동은 다음 단계다.

---

## 2. 완료

| 항목 | 비고 |
|------|------|
| 로그인/세션, JWT access+refresh, 역할 분리(admin/user/viewer) | [auth.md](features/auth.md) |
| 프로젝트·대화 CRUD | [projects-conversations.md](features/projects-conversations.md) |
| Artifact 위젯 렌더 + SQL 미리보기 | [widgets-artifact.md](features/widgets-artifact.md) |
| Stage 드래그·이동·리사이즈·자동 저장·복원, 채팅과 Stage 너비 조절 | [stage.md](features/stage.md) |
| Viewer 읽기 전용 화면(`/p/:id/view`) | [viewer.md](features/viewer.md) |
| Admin 유지 + 별도 AI 설정·DB 관리 패널 — DB 연결 등록/테스트, 역할별 테이블 권한 | [admin.md](features/admin.md) |
| SOC + Global Sales 샘플 DB, 서비스 DB Docker Compose 구성 | `docker-compose.yml` |
| 로컬 일반 스키마 데모용 Northwind, SKAX NMS 샘플 DB 시드 | `backend/scripts/seed_northwind_recent.py`, `seed_skax_nms.py` |
| Graph RAG 준비용 Neo4j 로컬 설치 | Community `2026.09.0`, 독립 Compose 서비스, 로컬 전용 Browser/Bolt, 인증·영속 볼륨·healthcheck. [설치 방법](../README.md#neo4j-로컬-설치-graph-rag-준비) |
| 로컬 문서 경로 등록·수동 Neo4j 적재 | 관리자 소스 등록·영속 저장·적재 상태, Markdown/텍스트 본문·문서 링크, 읽기 전용 공유, 재적재 중복 방지. 질문 검색 연동은 미구현. [graph-rag-sources.md](features/graph-rag-sources.md) |
| 실 LLM 전용 채팅 에이전트(OpenAI-compatible, Gemini) — 스키마 컨텍스트 전달, 실패 시 1회 복구 재시도, 그래도 안 되면 추측 없이 에러 반환(Mock 키워드 매칭 폴백은 2026-09-22 완전 삭제) | [chat.md](features/chat.md) |
| Provider별 AI 연결 설정·요청 분리, 로컬 OpenAI 호환 모델 지원 | [admin.md](features/admin.md) |
| `llm_usage` 사용량 기록 골격(테이블 적재) | [admin.md](features/admin.md) 데이터 모델 |
| 문서 체계 정비 — `AGENTS.md`/`CLAUDE.md`, `docs/01-folder-structure.md`, `docs/features/*.md`, 본 문서, `docs/dashboard.html`, `docs/kanban.html` | 이번 문서화 작업 1~5번 전체 완료 |
| DB별 예상 질문 유사도 DB — 전체 테이블 질문 생성 → 유사 질문 참조 답변 생성 | [similarity-search-design.md](features/similarity-search-design.md) |

## 3. 진행중

| 항목 | 비고 |
|------|------|
| 채팅 메시지 임베딩·유사도 검색(pgvector, `chat_vector` DB) | 백엔드 저장·검색(`message_embeddings.py`)까지 완료, API가 `related_messages` 반환. **프론트 미표시** — `App.jsx`가 아직 렌더링 안 함 |
| 실 LLM 경로 하드닝 | 기본 동작은 되나 재시도는 1회 한정, 레이트리밋/서킷브레이커 없음. [PROJECT_HANDOFF.md](../PROJECT_HANDOFF.md) 5번 |
| 운영 배포 파이프라인 | `compose.production.yml`, GitHub Actions(`deploy.yml`), `deployment/README.md` 절차는 있음. `deployment/README.md` 자체가 "GitHub Actions 첫 실행과 VPS 배포 결과는 완료 후 기록" 상태라고 명시 — 실제 운영 검증은 미완 |

## 4. 예정

| 항목 | 우선순위 | 비고 |
|------|----------|------|
| 질문 유사도 테스트 하니스 — 비슷한 질문이 같은 furniture를 내는지 검증 | HIGH | [PROJECT_HANDOFF.md](../PROJECT_HANDOFF.md) 1번, 2026-09-03 스냅샷 #7과 동일 항목, 미착수 |
| Circle 게이지 조합 카탈로그 (ring × size × companion) | MED | 스냅샷 #9와 동일, `ALLOWED_COMPONENTS`에 아직 없음 |
| Viewer에 남은 다크 Orion 자리표시(CSS `variant="orion"`) 정리 | LOW | [DESIGN.md](../DESIGN.md)가 "정식 토큰 아님"으로 명시. [viewer.md](features/viewer.md) 참고 |
| 실 RAG(문서 검색) 고도화 — 현재 `DocumentProvider`는 Mock 고정 문서만 | LOW | [chat.md](features/chat.md) 문서 근거 보강 절 |
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
