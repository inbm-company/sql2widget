# 기능: 관리자 — DB 연결 · 테이블 권한 · AI 설정

| 항목 | 내용 |
|------|------|
| 문서명 | 기능 문서 — 관리자 패널 |
| 기준일 | 2026-09-30 (구현 기준) |
| 관련 문서 | [chat.md](chat.md)(연결·권한·AI 설정이 실제로 쓰이는 곳) |
| 관련 코드 | `backend/app/repositories/connections.py`, `backend/app/crypto.py`, `backend/app/main.py`(`/api/database-connections*`, `/api/table-permissions`), `frontend/src/AdminPanel.jsx`, `frontend/src/api.js`(`getAiSettings`/`setAiSettings`) |

액터: 대부분 `admin`만. 그 외 역할은 403(패널 자체가 사이드바에 노출되지 않음, § [auth.md](auth.md)).

사이드바 하단에는 기존 `Admin` 버튼과 별도로 `AI 설정`, `DB 관리` 버튼이 있다. `Admin`은 기존 전체 설정을 유지한다. `AI 설정` 패널은 Provider별 AI 연결 설정만, `DB 관리` 패널은 연결 목록·테스트, 예상 질문 관리, 새 연결 등록, 테이블 권한을 표시한다. 세 패널은 같은 설정과 저장 동작을 공유하며 관리자에게만 노출된다.

---

## F-13 DB 연결 관리

`DB 관리`와 전체 `Admin` 패널에는 **Graph RAG 데이터 소스**도 표시된다. 로컬 폴더·파일 경로를 등록하고 별도의 **적재** 버튼으로 문서 본문과 명시된 문서 링크를 Neo4j에 저장한다. [지원 범위·API·접근 제한](graph-rag-sources.md).

| API | 기능 | 권한 |
|-----|------|------|
| `GET /api/database-connections` | 테넌트 연결 목록(비밀번호 비노출) | 로그인 |
| `POST /api/database-connections` | 연결 추가(host, port, database_name, username, password, sslmode) | admin |
| `POST /api/database-connections/{id}/test` | `SELECT 1`로 연결 테스트 | 로그인 |
| `GET /api/database-connections/{id}/tables` | `information_schema.tables` 베이스 테이블 목록 | 로그인 |
| `POST /api/database-connections/{id}/preview-sql` | 검증된 SELECT 실행(디버그용) | admin |

- 비밀번호는 `APP_SECRET`에서 유도한 키로 Fernet 대칭암호화해 `password_encrypted`에 저장(`crypto.encrypt_secret`). 조회 응답에는 절대 포함하지 않는다.
- `connection_url()`이 요청 시점에 복호화해 `postgresql://user:pass@host:port/db?sslmode=...` 형태로 조립.
- 새 연결 등록 폼 기본값은 로컬 SOC 데모 DB 접속정보(`db-customer` / `agent4any_customer_demo` / …) — 그대로 저장하면 로컬 컨테이너를 가리키므로 운영에서는 반드시 바꿔야 한다.
- `preview-sql`도 일반 채팅과 같은 읽기 전용 검증(`query.execute_readonly`)을 거친다 — admin이라고 DML이 뚫리지는 않는다.

## F-14 테이블 권한

| API | 기능 | 권한 |
|-----|------|------|
| `GET /api/table-permissions?connection_id=` | 연결별 역할-테이블 매핑 조회 | 로그인 |
| `PUT /api/table-permissions` | `{ connection_id, role, tables }`로 특정 역할의 허용 테이블 전체 교체 | admin |

- 저장은 delete-then-insert: 해당 `(tenant_id, connection_id, role)` 행을 지우고 새로 넣는다(`replace_table_permissions`).
- 현재 Admin UI는 **`user` 역할만** 편집 가능(체크박스 목록). `admin`/`viewer`용 허용 테이블은 시드 스크립트(`backend/scripts/seed_dev.py` 등)가 넣어둔 값을 UI에서 바꿀 방법이 아직 없다 — API 자체는 임의 role을 받는다.
- 이 목록이 채팅/미리보기 SQL의 `FROM`/`JOIN` 허용 테이블을 결정한다(§ [chat.md](chat.md) SQL 규칙). 행이 비어 있으면 SOC/Global 기본 테이블 집합으로 폴백.
- `schema_metadata()`가 이 허용 테이블만 골라 `information_schema`에서 컬럼·PK·FK를 읽어 실 LLM 프롬프트용 스키마 텍스트를 만든다 — 데이터 행은 절대 읽지 않는다.

## AI 연결 설정 (브라우저 로컬)

Admin 또는 별도 AI 설정 패널에서 Gemini, OpenAI 호환, 로컬 모델을 선택한다. 설정은 이 브라우저의 `localStorage`(`agent4any_ai_settings`)에 `{ provider, profiles: { gemini, openai, local } }` 형태로 저장한다. Provider를 바꾸면 해당 설정을 불러오며 모델·키를 다른 Provider로 복사하지 않는다. 미저장 입력은 패널 안에서 Provider별로 유지하고, **AI 설정 저장**을 누른 Provider를 요청에 사용한다. 기존 단일 설정은 원래 Provider의 프로필로 읽어 보존한다.

| 필드 | 동작 |
|------|------|
| Provider | Gemini / OpenAI 호환 / 로컬 모델(OpenAI 호환) |
| Model | Gemini 기본 `gemini-3.6-flash`, OpenAI 기본 `gpt-4o-mini`, 로컬은 설치된 모델 이름 직접 입력 |
| Base URL | OpenAI·로컬에서 입력 가능. 로컬 기본 `http://host.docker.internal:11434/v1`, Gemini는 Google 호환 URL 고정 |
| API key | `type="password"`, 로컬에서는 선택 사항 |
| Embedding model | 로컬에서 선택 입력. 없으면 채팅만 가능하고 예상 질문 생성·검색은 사용할 수 없음 |

- 저장한 값은 채팅과 예상 질문 생성·검색 요청의 `X-LLM-Provider`, `X-LLM-API-Key`, `X-LLM-Model`, `X-LLM-Base-URL`, `X-LLM-Embedding-Model` 헤더로 전달된다. 요청 설정이 서버 환경변수보다 우선한다.
- URL은 브라우저가 아니라 **백엔드에서 접근하는 주소**다. Docker Desktop에서는 호스트 서버에 `host.docker.internal`로 연결한다. 직접 실행하는 백엔드는 `http://localhost:11434/v1` 등을 쓴다. 서버는 별도로 실행해야 한다.
- 로컬 임베딩 벡터의 길이는 `CHAT_EMBEDDING_DIM`(기본 1536)과 정확히 일치해야 한다. 임의로 잘라 저장하지 않는다. 불일치하면 유사도 검색은 생략되고 예상 질문 저장은 실패한다.
- 키는 이 브라우저에만 남고 서버 DB에는 저장되지 않는다. 다른 Provider나 다른 서버 URL로 서버 기본 키를 전달하지 않는다.
- 이전 Gemini 모델 `gemini-2.5-flash`는 기존 동작대로 `gemini-3.6-flash`로 마이그레이션한다(`aiSettings.js`).

---

## 데이터 모델 (서비스 DB)

```text
database_connections(id, tenant_id, name, host, port, database_name,
                      username, password_encrypted, sslmode, created_by, created_at)
table_permissions(id, tenant_id, connection_id, role, schema_name, table_name)
llm_usage(id, tenant_id, user_id, conversation_id, provider, model,
          prompt_tokens, completion_tokens, total_tokens, success, error, created_at)
```

`llm_usage`는 이 패널에서 직접 보여주지 않는다 — 현재는 기록만 되는 골격(§ [PROJECT_HANDOFF.md](../../PROJECT_HANDOFF.md) 다음 작업 후보).

## 예상 질문 유사도 DB

AI 설정을 저장한 뒤 DB를 선택하고 **예상 질문 생성**을 누른다. 테이블 접근 역할을 고르거나 생성 개수를 지정하지 않는다. AI가 선택한 DB의 모든 테이블을 묶음별로 살펴보고 다양한 예상 질문과 SQL·위젯을 만든다. 코드는 읽기 전용 SQL을 검증하고 유효한 AI 질문만 임베딩해 저장한다. 진행률과 질문 수를 보여주며 중단되면 이어서 진행할 수 있다. 채팅에서는 기존 사용자 테이블 접근 제한을 적용한다. [예상 질문 유사도 상세](similarity-search-design.md).
