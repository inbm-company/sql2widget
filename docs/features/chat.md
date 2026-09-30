# 기능: 채팅 (에이전트)

| 항목 | 내용 |
|------|------|
| 문서명 | 기능 문서 — 채팅/에이전트 |
| 기준일 | 2026-09-21 (구현 기준) |
| 관련 문서 | [widgets-artifact.md](widgets-artifact.md)(Artifact 표시), [admin.md](admin.md)(연결·권한·AI 설정) |
| 관련 코드 | `backend/app/main.py`(`/api/chat`), `backend/app/agent_service.py`, `backend/app/agent.py`, `backend/app/llm.py`, `backend/app/query.py`, `backend/app/documents.py`, `backend/app/repositories/message_embeddings.py`, `frontend/src/App.jsx`(`Workspace.sendMessage`) |

이 기능이 제품의 핵심이다: 자연어 질문 → SQL 실행 → 위젯 Artifact. 다른 모든 기능(Stage, Viewer)은 여기서 나온 Artifact를 배치·조회하는 역할이다.

---

## F-07 고객 DB 선택

- 사이드바 "Database" 셀렉트. 목록은 `GET /api/database-connections`(테넌트 공유).
- 기본값은 목록의 첫 항목.
- 선택한 `connection_id`에 따라 사이드바 샘플 질문이 바뀐다: `dbconn_global` → Global 질문, `dbconn_northwind` → Northwind 질문, 그 외 → SOC 질문(`frontend/src/constants.js`).

## F-08 채팅 (핵심 흐름)

| 항목 | 내용 |
|------|------|
| 입력 | `conversation_id`, `message`, `connection_id`(선택) |
| 처리 | 1) user 메시지 저장 2) 첫 메시지로 대화 제목 갱신 3) 에이전트 실행 4) assistant 메시지 + artifact 저장 |
| 출력 | `user_message`, `assistant_message`, `artifact`, `meta`, `related_messages`, `embedding_provider`, `embedding_error` |
| UI | Enter 전송, Shift+Enter 줄바꿈. 실패 시 입력값 복원 + 오류 문구 |
| 타임아웃 | 프론트 채팅 요청 150초 (`frontend/src/api.js` `timeoutMs: 150000`) — 실 LLM 응답 + SQL 재시도(최대 1회 repair) 여유 |

### 에이전트 실행 경로 (`agent_service.run_agent`)

채팅 응답은 **항상 실 LLM 호출로만** 만든다. 키가 없거나 호출이 실패하면 추측으로 대신 답하지 않고 에러를 그대로 올린다 — 예전에 있던 SOC/Global 키워드 매칭 폴백(`run_mock_agent`)은 완전히 삭제됨(2026-09-22). 다른 커넥션(Northwind, SKAX NMS 등)에는 애초에 대응하지 못한 채 SOC 안내문을 잘못 보여주는 문제가 있었기 때문.

1. **연결/권한 해석** — `connection_id`가 있으면 해당 연결과, 사용자 역할(`user_role`)에 대한 `table_permissions`를 조회. 권한 행이 비어 있으면 SOC(또는 `dbconn_global`이면 Global) 기본 테이블 집합으로 폴백.
2. **스키마 텍스트 구성** — 선택된 연결의 허용 테이블만으로 스키마 텍스트를 만든다(`_schema_text_for_connection`).
3. **명령 유사도 검색·LLM 호출** — 명령을 임베딩해 선택한 DB의 `command_catalog`에서 유사한 명령을 검색한다. 명령·SQL·위젯 계획을 `matched_commands`로 LLM에 전달하고, 응답의 `meta.command_retrieval`에 상태·유사도·DB 정보·실행 계획을 포함한다. [명령 유사도 상세](similarity-search-design.md). `plan_with_llm()`의 플랜이 비면(키 없음/호출 실패/파싱 실패 등 사유 무관) **바로 `AgentRunError`를 던져 `/api/chat`이 HTTP 502 + 실제 에러 메시지를 그대로 반환**한다.
4. **SQL 실행** — 플랜이 있으면 `_materialize_plan()`으로 각 위젯의 `sql`을 읽기 전용 실행 → 결과를 컴포넌트별 props로 변환(`rows_to_props`).
5. **1회 복구 재시도** — SQL/JSON 실행이 실패하면 실패 사유를 `repair_hint`로 넣어 LLM에 재요청. 그것도 실패하면 (Mock 폴백 없이) `AgentRunError`를 던진다.
6. **문서 근거 보강** — 질문 또는 위젯 제목에 "공격"/"attack"이 있으면 `DocumentProvider.search()`로 관련 문서를 찾아 `MarkdownBlock`(해결 방안) + `SourceList`(출처) 위젯을 추가. 출처가 없으면 근거 없는 해결 방안을 지어내지 않는다.
7. **사용량 기록** — 실 LLM 호출마다 `llm_usage`에 provider/model/토큰 수/성공 여부를 기록(`llm.log_usage`).

### LLM 프로바이더

| 항목 | 내용 |
|------|------|
| 지원 | OpenAI-compatible(`LLM_BASE_URL` + `LLM_MODEL`), Gemini(OpenAI 호환 엔드포인트 `https://generativelanguage.googleapis.com/v1beta/openai`로 매핑, 기본 모델 `gemini-3.6-flash`) — 둘 다 `llm._post_openai_compatible()`이라는 같은 HTTP 호출 헬퍼를 공유(`Authorization: Bearer <key>`) |
| 런타임 오버라이드 | 브라우저 Admin의 "AI 연결" 설정(§ [admin.md](admin.md))이 요청 헤더(`X-LLM-Provider`, `X-LLM-API-Key`, `X-LLM-Model`)로 전달되면 서버 `.env` 설정보다 우선 |
| 실패 시 | 키가 없거나 호출이 실패하면 **HTTP 502 + 실제 에러 메시지를 그대로 노출**한다. 조용한 폴백 없음. |
| 스키마 컨텍스트 | 선택한 연결의 역할별 허용 테이블에 한해 테이블·컬럼·타입·PK/FK 관계를 프롬프트에 전달(`connections.schema_context_for_connection`). **실제 데이터 행과 연결 비밀번호는 전달하지 않는다.** |

### SQL 규칙 (`backend/app/query.py`)

- `SELECT` 또는 `WITH`로 시작해야 하며, 단일 문장만(세미콜론으로 이어붙인 다중 문장 금지).
- `INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE/CREATE/GRANT/REVOKE/COPY/CALL/DO/EXECUTE/MERGE/…` 등 쓰기·DDL·권한 키워드가 있으면 거부.
- `FOR UPDATE`/`FOR SHARE` 같은 락 절 금지.
- `FROM`/`JOIN` 대상 테이블은 역할별 허용 목록(`allowed_tables`)에 있어야 함(대소문자 무시, 스키마 접두사는 마지막 토큰만 비교).
- 커넥션은 `conn.read_only = True`로 열고 `statement_timeout`을 초 단위로 설정(기본 10초), 결과는 최대 1000행(`fetchmany`).
- 실행 결과의 `Decimal`/날짜/`UUID`/바이트 등은 JSON 직렬화 가능한 타입으로 변환(`jsonable`).

### 채팅 메시지 임베딩 (진행중 — 백엔드만 동작)

- 메시지를 보내면 `llm.embed_text()`로 사용자 메시지를 임베딩(Gemini `gemini-embedding-001` 또는 OpenAI `text-embedding-3-small`, `CHAT_EMBEDDING_DIM` 차원). 채팅 완성과 같은 `_post_openai_compatible()` 헬퍼·인증 방식을 공유한다.
- 키가 없거나 provider가 인식 불가면 조용히 건너뛴다(`embedding_provider: "mock"`, `embedding_error: null`) — 이건 "에러를 숨기는 폴백"이 아니라 임베딩이 선택 기능이라 응답 자체는 그대로 내려가는 것. 실제로 호출했는데 실패한 경우에만 `embedding_error`에 원인이 채워진다.
- 응답의 `embedding_provider` 필드로 실제 어떤 provider가 쓰였는지(`"gemini"`/`"openai"`/`"mock"`) 항상 명확히 알 수 있다 — DB를 직접 조회하지 않고도 mock인지 실제 호출인지 구분 가능(2026-09-22 추가).
- 임베딩이 만들어지면 별도 `chat_vector` DB(pgvector)에 저장하고, 코사인 유사도로 같은 테넌트의 과거 메시지 상위 5개를 찾아 `related_messages`로 응답에 포함한다. assistant 응답도 같은 방식으로 임베딩·저장된다.
- **주의**: `related_messages`/`embedding_provider`/`embedding_error`는 API 응답에는 있지만 `frontend/src/App.jsx`가 아직 렌더링하지 않는다 — 백엔드 스캐폴드만 완료된 상태.

---

## API

| Method | Path | 권한 |
|--------|------|------|
| POST | `/api/chat` | 로그인 (viewer도 API 자체는 호출 가능하지만 UI에서 버튼을 막아 실질적으로 차단) |
| GET | `/api/database-connections` | 로그인 |
