# 기능: 채팅 (에이전트)

| 항목 | 내용 |
|------|------|
| 문서명 | 기능 문서 — 채팅/에이전트 |
| 기준일 | 2026-10-01 (구현 기준) |
| 관련 문서 | [widgets-artifact.md](widgets-artifact.md)(Artifact 표시), [admin.md](admin.md)(연결·권한·AI 설정) |
| 관련 코드 | `backend/app/main.py`(`/api/chat`), `backend/app/intent_router.py`, `backend/app/schema_linking.py`, `backend/app/graph_answer.py`, `backend/app/agent_service.py`, `backend/app/agent.py`, `backend/app/llm.py`, `backend/app/query.py`, `backend/app/documents.py`, `backend/app/repositories/message_embeddings.py`, `frontend/src/App.jsx`(`Workspace.sendMessage`), `frontend/src/ChatTrace.jsx`, `backend/app/chat_trace.py` |

이 기능이 제품의 핵심이다: 자연어 질문 → SQL 실행 → 위젯 Artifact. 다른 모든 기능(Stage, Viewer)은 여기서 나온 Artifact를 배치·조회하는 역할이다.

---

## F-07 고객 DB 선택

- 사이드바 "Database" 셀렉트. 목록은 `GET /api/database-connections`(테넌트 공유).
- 기본값은 목록의 첫 항목.
- 선택한 `connection_id`에 따라 사이드바 샘플 질문이 바뀐다: `dbconn_global` → Global 질문, `dbconn_northwind` → Northwind 질문, 그 외 → SOC 질문(`frontend/src/constants.js`).

## F-08 채팅 (핵심 흐름)

| 항목 | 내용 |
|------|------|
| 입력 | `conversation_id`, `message`, `connection_id`(선택), `route`(선택 — 되묻기 버튼으로 사용자가 고른 경로) |
| 처리 | 1) user 메시지 저장 2) 첫 메시지로 대화 제목 갱신 3) 에이전트 실행 4) assistant 메시지 + artifact + 표시용 meta 저장 |
| 출력 | `user_message`, `assistant_message`, `artifact`, `meta`, `related_messages`, `embedding_provider`, `embedding_error` |
| UI | Enter 전송, Shift+Enter 줄바꿈. 실패 시 입력값 복원 + 오류 문구 |
| 타임아웃 | 프론트 채팅 요청 150초 (`frontend/src/api.js` `timeoutMs: 150000`) — 실 LLM 응답 + SQL 재시도(최대 1회 repair) 여유 |

### 의도 라우팅 (`intent_router.decide_route`)

`run_agent`는 SQL 계획을 세우기 전에 메시지를 어떤 경로로 처리할지 먼저 정한다. 결과는 `meta.route`(`data_query` / `schema_qa` / `knowledge_qa` / `graph_build` / `clarify`), `meta.route_source`(`user_choice` / `jev` / `llm_fallback`)로 응답에 남는다. 예상 질문 유사도는 경로 결정에 쓰지 않고 `data_query`의 SQL 계획에만 쓴다. 전체 흐름도는 [dashboard.html](../dashboard.html)의 채팅 절에 있다.

| 순서 | 판단 | 비고 |
|------|------|------|
| 1 | 요청에 `route`가 있으면 그대로 사용 | 되묻기 버튼을 누른 경우. 모델 호출 없음 |
| 2 | TypeSafe **Jev** Choice 질문(`POST {TYPESAFE_BASE_URL}/v1/systemone`)으로 분류 | `TYPESAFE_API_KEY` 필요. 429/529/네트워크 오류는 최대 2회 재시도(0.5초·1초 백오프), 401/422 등은 재시도 없이 즉시 실패 |
| 3 | Jev를 못 쓰면 채팅 LLM(`json_with_llm`)이 경로를 선택 | `meta.route_source = "llm_fallback"`, `meta.route_jev_error`에 사유 기록 — 숨기지 않는다 |
| 4 | 그 LLM도 실패하면 `AgentRunError` → HTTP 502 | |

Jev의 `confidence`가 `ROUTE_MIN_CONFIDENCE`(기본 0.5) 미만이거나 결과가 `other`면 **되묻기**(`clarify`)로 처리한다. 임계값은 실제 질문 데이터로 검증되지 않은 초기값이다.

| 경로 | 동작 |
|------|------|
| `data_query` | 아래 "에이전트 실행 경로" 그대로(SQL + 위젯) |
| `schema_qa` | 허용된 스키마 텍스트만으로 LLM이 테이블·컬럼 구조를 설명. SQL 실행 없음. `MarkdownBlock` 위젯 1개 |
| `knowledge_qa` | 프로젝트 문서에서 추출한 엔티티·관계·근거로 답한다(위 "문서 그래프로 답하기" 절). 추출된 엔티티가 없으면 안내와 선택지 |
| `graph_build` | 업로드한 문서를 지식그래프로 만드는 협의·승인·추출 흐름(관리자 전용, DB 연결 불필요). `graph_action`이 있으면 버튼 동작으로 바로 처리. 자세한 동작은 [graph-rag-sources.md](graph-rag-sources.md) 채팅 연동 절 |
| `clarify` | 위젯 없이 선택지 버튼(`artifact.type = "choices"`, `artifact.choices[{label, route, message}]`)을 반환. 버튼을 누르면 같은 메시지를 `route`와 함께 다시 전송하므로 대화에 사용자 메시지가 한 번 더 남는다. 선택지는 assistant 메시지의 artifact에 저장되어 새로고침 후에도 유지된다 |

### 문서 그래프로 답하기 (`graph_answer.handle`, `knowledge_qa`)

"문서에서 …", "문서에 따르면 …"처럼 문서에 적힌 내용을 묻는 질문은 프로젝트의 **추출된 엔티티**로 답한다. SQL은 실행하지 않는다.

1. **읽기** — `project_graph.project_entities`(고정 Cypher, 테넌트·프로젝트 범위 고정)로 활성 엔티티(최대 500, 타입별로 공평하게 나눈 표본)·관계·원문 근거를 읽고, 타입별 정확한 개수(`type_counts`)와 전체 개수는 별도 집계로 함께 읽는다. LLM이 Cypher를 쓰지 않는다.
2. **좁히기** — 엔티티가 40개를 넘으면 채팅 LLM이 "타입·이름·설명" 목록에서 관련 이름을 고르고(최대 15), 코드가 그 엔티티와 직접 이웃을 모은다(최대 40). 40개 이하이면 고르는 호출 없이 전부 쓴다.
3. **답하기** — 채팅 LLM이 `facts`(타입별 개수, 엔티티와 속성·근거 문장, 관계)만으로 답한다. 문서에 없으면 없다고 답하게 한다. 답변이 근거로 쓴 엔티티 이름(`used`)을 함께 받는다.
4. **위젯** — 코드가 만든다(LLM이 값을 지어내지 않음): `MarkdownBlock`(문서 기반 답변), 근거 `DataTable`(타입·이름·설명·문서 소스), 근거 사이의 관계 `DataTable`, 근거 문장이 속한 제목의 `SourceList`.
5. **응답 `meta.knowledge`** — `entities_total`, `truncated`, `picked`, `entities_in_prompt`, `used`.

| 상황 | 동작 |
|------|------|
| 프로젝트에 추출된 엔티티가 없음 | 안내 + 선택지(`graph_build`는 관리자에게만, `data_query`, `schema_qa`) |
| 좁히기에서 관련 엔티티 없음 | "찾지 못했어요" + 선택지. 답을 지어내지 않음 |
| Neo4j·LLM 실패 | HTTP 502 + 사유(조용한 대체 없음) |

- **라우팅**: Jev 상태에 `has_document_graph`(프로젝트 소스 중 추출된 엔티티가 있는지)를 넘긴다. 문서가 DB 구조를 설명하는 경우에도 질문이 문서를 근거로 말하면 `knowledge_qa`, 문서 언급 없이 연결된 DB의 구조를 물으면 `schema_qa`다. 두 답은 출처가 달라 값이 다를 수 있다(Northwind: 문서 16개 테이블 vs 실제 DB 15개).
- **한계**: 엔티티 500개를 넘는 그래프는 표본만 읽는다(`truncated`). "몇 개" 질문은 정확한 집계로 답하지만, 표본에서 빠진 엔티티(주로 컬럼)의 내용 질문은 답하지 못할 수 있다. 응답에는 불완전할 수 있다는 안내가 붙는다. Table 170·Column 1,038 소스에서 "테이블 몇 개"(170)·"컬럼 몇 개"(1,038)·"뷰 목록"(4개)에 정확히 답했다. 엔티티 타입은 문서마다 승인된 스키마를 따르므로 `Table`이 아닌 타입에도 동작하지만 검증한 것은 Northwind 문서 1개다.

### 스키마 줄이기 (`schema_linking.link_from_matches`)

허용 테이블이 많은 DB는 전체 컬럼을 프롬프트에 넣으면 크고 느려진다(Northwind 기준 테이블당 약 320자 → 100개면 약 3.2만 자). `data_query`는 SQL 계획 전에 **관련 테이블만** 스키마로 넘긴다. 1순위는 유사 질문, 없으면 프로젝트 문서 그래프의 테이블 설명이다(`schema_linking.link_schema`).

| 조건 | 계획용 스키마 | `meta.schema_link` |
|------|---------------|--------------------|
| 허용 테이블 ≤ `SCHEMA_LINK_MIN_TABLES`(기본 20) | 전체 | `{source: "full", reason: "small_schema"}` |
| 매칭된 질문의 SQL(`FROM`/`JOIN`)에서 허용 테이블을 찾음 | 매칭 질문들의 테이블 합집합만. 모델 호출 없음 | `{source: "similarity", tables: [...], total: N}` |
| 위가 아니고, 프로젝트 문서 그래프에 설명된 `Table` 엔티티가 있음 | 채팅 LLM이 "이름+설명" 목록에서 고른 테이블만 | `{source: "graph", tables: [...], total: N}` |
| 그래프도 쓸 수 없음 | 전체 | `{source: "full", reason, error?}` — `reason`: `no_project`(프로젝트 없음) / `graph_unavailable`(Neo4j 오류, `error`에 사유) / `no_documented_tables`(설명된 테이블 없음) / `no_tables_picked`(고른 결과가 비었거나 허용 밖, 호출 실패 시 `error`) |

- **그래프 경로**: 허용 테이블 전체의 이름을 목록으로 주고(문서에 없는 테이블은 설명 없이 이름만), 목록의 이름만 고르게 한다. 목록은 고정 Cypher(`project_graph.project_table_catalog`, 테넌트·프로젝트 범위 고정)로 읽으며 LLM이 Cypher를 쓰지 않는다. 결과는 허용 테이블로 다시 제한한다. 한국어 질문과 영어 테이블명은 설명으로 이어진다.
- 컬럼·타입은 문서가 아니라 **실제 DB 메타데이터**에서 만든다(문서는 낡았을 수 있음). FK 이웃 확장은 하지 않는다(Northwind 실험에서 정확도 이득 없이 스키마만 2배).
- 줄인 스키마로 SQL이 실패하면 1회 복구 재시도는 **전체 스키마**로 한다(`escalated_to_full: true`).
- CTE 이름과 역할이 읽을 수 없는 테이블은 제외한다.
- `schema_qa`는 항상 전체 스키마를 쓴다(구조 질문이므로).
- Northwind(15개 테이블, 임계값을 5로 낮춘 실행)로 확인: 유사 질문 경로 2개 질문, 그래프 경로 5개 질문(유사 질문 검색만 이 프로세스에서 끔)이 모두 재시도 없이 성공. 사전 비교 실험(10개 질문)에서는 시드만 쓴 결과가 전체 스키마 결과와 모두 일치했고 스키마 크기는 평균 23%였다.
- 100개 이상 DB(SKAX NMS)는 그래프 소스가 없어 미검증. 목록 크기는 100개일 때 약 8천 자로 추정.
- **알려진 문제(이번 변경과 무관)**: SQL 검증기가 `EXTRACT(YEAR FROM AGE(...))`의 `FROM AGE`를 테이블로 오인해 `Table not permitted: AGE`로 거부한다. 전체 스키마에서도 재현되며, 복구 재시도로 넘어가는 경우가 있다.

### 에이전트 실행 경로 (`agent_service.run_agent`)

채팅 응답은 **항상 실 LLM 호출로만** 만든다. 키가 없거나 호출이 실패하면 추측으로 대신 답하지 않고 에러를 그대로 올린다 — 예전에 있던 SOC/Global 키워드 매칭 폴백(`run_mock_agent`)은 완전히 삭제됨(2026-09-22). 다른 커넥션(Northwind, SKAX NMS 등)에는 애초에 대응하지 못한 채 SOC 안내문을 잘못 보여주는 문제가 있었기 때문.

1. **연결/권한 해석** — `connection_id`가 있으면 해당 연결과, 사용자 역할(`user_role`)에 대한 `table_permissions`를 조회. 권한 행이 비어 있으면 SOC(또는 `dbconn_global`이면 Global) 기본 테이블 집합으로 폴백.
2. **스키마 텍스트 구성** — 선택된 연결의 허용 테이블만으로 스키마 텍스트를 만든다(`_schema_text_for_connection`).
3. **예상 질문 유사도 검색·LLM 호출** — 질문을 임베딩해 선택한 DB의 `question_catalog`에서 유사한 예상 질문을 검색한다. 현재 사용자가 접근 가능한 테이블의 SQL만 `matched_questions`로 LLM에 전달하고, 응답의 `meta.question_retrieval`에 상태·유사도·DB 정보·실행 계획을 포함한다. [예상 질문 유사도 상세](similarity-search-design.md). `plan_with_llm()`의 플랜이 비면(키 없음/호출 실패/파싱 실패 등 사유 무관) **바로 `AgentRunError`를 던져 `/api/chat`이 HTTP 502 + 실제 에러 메시지를 그대로 반환**한다.
4. **SQL 실행** — 플랜이 있으면 `_materialize_plan()`으로 각 위젯의 `sql`을 읽기 전용 실행 → 결과를 컴포넌트별 props로 변환(`rows_to_props`).
5. **1회 복구 재시도** — SQL/JSON 실행이 실패하면 실패 사유를 `repair_hint`로 넣어 LLM에 재요청. 그것도 실패하면 (Mock 폴백 없이) `AgentRunError`를 던진다.
6. **문서 근거 보강** — 질문 또는 위젯 제목에 "공격"/"attack"이 있으면 `DocumentProvider.search()`로 관련 문서를 찾아 `MarkdownBlock`(해결 방안) + `SourceList`(출처) 위젯을 추가. 출처가 없으면 근거 없는 해결 방안을 지어내지 않는다.
7. **사용량 기록** — 실 LLM 호출마다 `llm_usage`에 provider/model/토큰 수/성공 여부를 기록(`llm.log_usage`).

### 채팅 처리 내역 (새로고침 후 유지)

답변 위의 **처리 내역**을 펼치면 선택 경로·분류 방식(Jev / 채팅 LLM 폴백 / 사용자 선택)·분류 확신·답변 모델을 확인한다. 그래프 사용 여부는 실행 결과로 표시하며, 그래프 구성은 문서 질문 답변과 구분한다.

- `assistant_message.meta`와 대화 조회의 `messages[].meta`에 표시용 처리 내역을 저장한다(`messages.meta`, 마이그레이션 `010_message_meta.sql`). 기존 최상위 `meta` 응답은 유지한다.
- 문서 질문의 `knowledge`에는 `status`, 그래프 전체 `entities_total`/`relations_total`, 실제 읽은 `entities_read`/`relations_read`, `truncated`, 답변 모델에 전달한 `entities_in_prompt`/`relations_in_prompt`와 `prompt_entities`를 기록한다. 500개 한도 조회는 전체 개수와 구분한다.
- `used_entities`는 모델이 사용했다고 보고한 엔티티의 ID·타입·이름·문서 소스·원문 근거다. `used_relations`는 보고된 엔티티 사이의 관계다. 실제 조회·전달 사실과 모델의 사용 보고를 구분하며, 정확성은 원문과 대조한다. 모델이 보고하지 않으면 빈 목록으로 표시한다.
- SQL의 `schema_link`는 그래프 기반 테이블 선택·실패/미사용 사유·전체 스키마 복구 재시도·대응되는 테이블 설명 수와 선택한 설명을 표시한다. `question_retrieval`은 검색 상태·참고 질문 수·질문/유사도를 표시한다.
- `graph_build`에는 응답 당시 소스·스키마/추출 상태·엔티티/관계 수를 기록한다. 백그라운드 진행 상태는 기존 그래프 카드에서 갱신하며, 처리 내역은 응답 당시 기록이다.
- 표시용 기록은 허용된 필드만 저장하며 API 키·요청 헤더·원시 오류·유사 질문 SQL 계획을 포함하지 않는다. 서버 로그·감사 로그에 문서 본문을 추가하지 않는다. 최종 HTTP 502 오류는 기존 오류 화면을 유지한다.
- 기존 답변은 `meta=null`로 **기록 없음**을 표시한다. 과거 사용 여부를 추정하거나 재계산하지 않는다.

### LLM 프로바이더

| 항목 | 내용 |
|------|------|
| 지원 | OpenAI 호환, Gemini(기존 Google OpenAI 호환 API 유지), 로컬 OpenAI 호환 서버. `providers/openai.py`, `gemini.py`, `local.py`가 요청·응답을 담당하고 `providers/transport.py`가 HTTP 전송을 공유한다. 프롬프트는 `prompts.py`, 공통 진입점·사용량 기록은 `llm.py`에 있다. |
| 런타임 오버라이드 | 브라우저 Admin의 "AI 연결" 설정(§ [admin.md](admin.md))이 요청 헤더(`X-LLM-Provider`, `X-LLM-API-Key`, `X-LLM-Model`, `X-LLM-Base-URL`, `X-LLM-Embedding-Model`)로 전달되면 서버 `.env` 설정보다 우선 |
| 실패 시 | 클라우드 키가 없거나 호출이 실패하면 **HTTP 502 + 실제 에러 메시지를 그대로 노출**한다. 조용한 폴백 없음. |
| 스키마 컨텍스트 | 선택한 연결의 역할별 허용 테이블에 한해 테이블·컬럼·타입·PK/FK 관계를 프롬프트에 전달(`connections.schema_context_for_connection`). **실제 데이터 행과 연결 비밀번호는 전달하지 않는다.** |

로컬 모델은 API 키가 선택 사항이며 채팅 모델 이름과 Base URL이 필요하다. 임베딩 모델이 없거나 차원이 `CHAT_EMBEDDING_DIM`과 다르면 유사도 검색을 생략하고 실모델 채팅은 계속한다. 예상 질문 생성·저장은 유효한 임베딩 모델이 필요하다. 다른 Provider의 서버 키를 가져와 사용하지 않는다.

### SQL 규칙 (`backend/app/query.py`)

- `SELECT` 또는 `WITH`로 시작해야 하며, 단일 문장만(세미콜론으로 이어붙인 다중 문장 금지).
- `INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE/CREATE/GRANT/REVOKE/COPY/CALL/DO/EXECUTE/MERGE/…` 등 쓰기·DDL·권한 키워드가 있으면 거부.
- `FOR UPDATE`/`FOR SHARE` 같은 락 절 금지.
- `FROM`/`JOIN` 대상 테이블은 역할별 허용 목록(`allowed_tables`)에 있어야 함(대소문자 무시, 스키마 접두사는 마지막 토큰만 비교).
- 커넥션은 `conn.read_only = True`로 열고 `statement_timeout`을 초 단위로 설정(기본 10초), 결과는 최대 1000행(`fetchmany`).
- 실행 결과의 `Decimal`/날짜/`UUID`/바이트 등은 JSON 직렬화 가능한 타입으로 변환(`jsonable`).

### 채팅 메시지 임베딩 (진행중 — 백엔드만 동작)

- 메시지를 보내면 `llm.embed_text()`로 사용자 메시지를 임베딩(Gemini `gemini-embedding-001`, OpenAI `text-embedding-3-small`, 로컬은 지정한 임베딩 모델). `CHAT_EMBEDDING_DIM` 차원을 사용하며 Provider 어댑터와 공통 HTTP 전송을 거친다. 로컬에서는 키가 선택 사항이다.
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
