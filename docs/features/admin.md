# 기능: 관리자 — DB 연결 · 테이블 권한 · AI 설정

| 항목 | 내용 |
|------|------|
| 문서명 | 기능 문서 — 관리자 패널 |
| 기준일 | 2026-10-15 (Together AI 추가) |
| 관련 문서 | [chat.md](chat.md)(연결·권한·AI 설정이 실제로 쓰이는 곳) |
| 관련 코드 | `backend/app/repositories/connections.py`, `backend/app/crypto.py`, `backend/app/local_models.py`, `backend/app/main.py`(`/api/ai/local-models`, `/api/database-connections*`, `/api/table-permissions`), `frontend/src/AdminPanel.jsx`, `frontend/src/api.js`(`getAiSettings`/`setAiSettings`) |

액터: 대부분 `admin`만. 그 외 역할은 403(패널 자체가 사이드바에 노출되지 않음, § [auth.md](auth.md)).

사이드바 하단에는 기존 `Admin` 버튼과 별도로 `AI 설정`, `DB 관리` 버튼이 있다. `Admin`은 기존 전체 설정을 유지한다. `AI 설정` 패널은 Provider별 AI 연결 설정과 Jev 공통 키 입력, `DB 관리` 패널은 연결 목록·테스트, 예상 질문 관리, 새 연결 등록, 테이블 권한을 표시한다. 세 패널은 같은 설정과 저장 동작을 공유하며 관리자에게만 노출된다.

드로어는 닫기 버튼 또는 패널 바깥의 어두운 배경을 클릭하면 닫힌다. 패널 내부를 클릭하면 열린 상태를 유지한다.

---

## F-13 DB 연결 관리


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
- SKAX NMS는 로컬·운영에서 `SKAX NMS DB`(`dbconn_skax_nms`) 연결로 자동 등록한다. 운영은 별도 `db-skax-nms` 서비스와 영속 볼륨에 저장소 스냅샷을 최초 복원하고, admin/user/viewer의 `cinamon` 테이블·뷰 권한을 등록한다. 재배포는 기존 DB를 보존하며 연결·권한을 다시 등록한다. 배포 완료 전 읽기 전용 접속과 역할별 권한을 검사한다. [운영 절차](../../deployment/README.md#skax-nms-cinamon-운영-db).

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

Admin 또는 별도 AI 설정 패널에서 Gemini, OpenAI 호환, Together AI, 로컬 모델을 선택한다. 설정은 이 브라우저의 `localStorage`(`sql2widget_ai_settings`)에 `{ provider, profiles: { gemini, openai, together, local }, jevApiKey }` 형태로 저장한다. 모델·키는 Provider별 프로필에, Jev 키는 최상위 공통 설정에 보관한다. Provider를 바꾸면 해당 설정을 불러오며 모델·키를 다른 Provider로 복사하지 않는다. 미저장 입력은 패널 안에서 Provider별로 유지하고, **AI 설정 저장**을 누른 Provider를 요청에 사용한다. 기존 단일 설정은 원래 Provider의 프로필로 읽어 보존한다.

| 필드 | 동작 |
|------|------|
| Provider | Gemini / OpenAI 호환 / Together AI / 로컬 모델(OpenAI 호환) |
| Model | Gemini 기본 `gemini-3.8-flash`, OpenAI 기본 `gpt-4o-mini`, Together 기본 `Qwen/Qwen3.5-9B`, 로컬은 서버의 `/models` 목록에서 선택(조회 실패 시 직접 입력) |
| Base URL | OpenAI·Together·로컬에서 입력 가능. 로컬 기본 `http://host.docker.internal:11434/v1`, Gemini는 Google 호환 URL 고정 |
| API key | `type="password"`, 로컬에서는 선택 사항 |
| Embedding model | 로컬에서 같은 목록에서 선택(선택 사항, 조회 실패 시 직접 입력). 없으면 채팅만 가능하고 예상 질문 생성·검색은 사용할 수 없음 |
| Jev API key | `type="password"`, Provider 공통 의도 분류 키. 공백 제거 후 저장, 빈 값은 서버 설정 사용 |

- 저장한 값은 채팅과 예상 질문 생성·검색 요청의 `X-LLM-Provider`, `X-LLM-API-Key`, `X-LLM-Model`, `X-LLM-Base-URL`, `X-LLM-Embedding-Model` 헤더로 전달된다. 요청 설정이 서버 환경변수보다 우선한다.
- URL은 브라우저가 아니라 **백엔드에서 접근하는 주소**다. Docker Desktop에서는 호스트 서버에 `host.docker.internal`로 연결한다. 직접 실행하는 백엔드는 `http://localhost:11434/v1` 등을 쓴다. 서버는 별도로 실행해야 한다.
- 로컬 Provider는 패널을 열 때와 **모델 목록 새로고침** 클릭 시 `POST /api/ai/local-models`(관리자 전용, body `{base_url, api_key}`)를 호출한다. 백엔드가 `{base_url}/models`(OpenAI 호환, 타임아웃 5초)를 조회해 `{models: [id…]}`를 반환하고, 실패하면 400과 원인 메시지를 돌려주며 UI는 직접 입력으로 되돌아간다. 저장된 모델이 목록에 없어도 선택지에 유지된다.
- 로컬 임베딩 벡터의 길이는 `CHAT_EMBEDDING_DIM`(기본 1536)과 정확히 일치해야 한다. 임의로 잘라 저장하지 않는다. 불일치하면 유사도 검색은 생략되고 예상 질문 저장은 실패한다.
- 키는 이 브라우저에만 남고 서버 DB에는 저장되지 않는다. 다른 Provider나 다른 서버 URL로 서버 기본 키를 전달하지 않는다.
- Gemini 기본값만 `gemini-3.8-flash`로 변경했다. 저장된 `gemini-3.6-flash`와 사용자 지정 다른 모델·API 키·임베딩 모델·Jev 키·다른 Provider 프로필은 유지한다. 기존 `gemini-2.5-flash`를 기본 모델로 전환하는 규칙은 유지한다(`aiSettings.js`). 백엔드 Gemini Provider도 모델 지정이 없으면 `gemini-3.8-flash`를 사용한다.


### Together AI

**AI 설정 → Provider → Together AI**를 선택하고 Together API 키를 입력한 뒤 저장한다. 기본 Base URL은 `https://api.together.ai/v1`, 채팅 모델은 `Qwen/Qwen3.5-9B`다. 모델·URL·키는 `together` 프로필에 따로 보관하며 기존 Gemini/OpenAI/로컬 설정과 Jev 공통 키를 유지한다. 서버 설정을 사용할 때도 기존 `LLM_PROVIDER=together`, `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`을 사용한다. 환경변수에 모델·URL을 명시했다면 해당 값을 Together용으로 함께 바꿔야 한다.

사용자가 제시한 `openai/gpt-oss-20b`는 [공식 제공 종료 목록](https://docs.together.ai/docs/deprecations)에 있으므로 기본값으로 사용하지 않는다. 사용할 수 있는 전용 엔드포인트가 있다면 Model과 Base URL을 직접 지정할 수 있다. 기본 모델은 [현재 서버리스 목록](https://docs.together.ai/docs/serverless/models)에 있는 공식 대체 모델이다. 호출은 기존 [OpenAI 호환 API](https://docs.together.ai/docs/inference/openai-compatibility)를 재사용하며 별도 SDK를 설치하지 않는다.

Together는 현재 서버리스 임베딩 모델을 제공하지 않는다. 임베딩 기본값은 비워 두고, 미설정 호출은 명시적인 오류를 반환한다. 별도 임베딩 공급자로 자동 전환하거나 다른 프로필의 키를 재사용하지 않는다. 같은 Base URL에서 호출 가능한 전용 모델이 있을 때만 **Embedding model**에 지정한다. 임베딩 요청에는 `dimensions`를 보내지 않으며 반환된 원래 차원을 확인한다.

채팅의 SQL 계획·위젯 생성에는 Together를 사용할 수 있다. 예상 질문 유사도 검색과 메시지 임베딩은 별도 전용 임베딩 모델이 없으면 사용하지 못한다. 전용 모델의 벡터 차원은 서버 `CHAT_EMBEDDING_DIM`(기본 1,536)과 일치해야 하며 자동 절단·패딩하지 않는다. 기존 벡터 데이터를 자동 변경하지 않는다.

## Jev 의도 분류 연결

관리자의 **AI 설정 → Jev API key**에 키를 입력하고 **AI 설정 저장**을 누르면 다음 채팅 요청부터 사용한다. 모든 Provider가 이 앱의 공통 Jev 키를 사용하므로 Provider 전환과 새로고침 후에도 유지된다. doc2graph의 키를 자동으로 가져오지 않는다.

- 브라우저 키는 `POST /api/chat`의 `X-Jev-API-Key` 헤더로만 전달한다. 메시지 본문, 예상 질문 생성·검색, DB 연결 조회, 로컬 모델 목록 요청에는 넣지 않는다.
- 요청 키를 우선 사용하며 비어 있거나 헤더가 없으면 서버 `TYPESAFE_API_KEY`를 사용한다. 서버 키도 없거나 Jev가 실패하면 기존처럼 채팅 LLM이 분류한다.
- 브라우저와 서버는 8,192자 이하의 한 줄 문자열만 허용한다. 저장 오류는 설정 화면에 표시하고, 잘못된 헤더는 메시지를 저장하기 전에 HTTP 400으로 거부한다.
- 키는 Jev 인증에만 사용한다. 분류 payload, SQL 계획·복구·답변·임베딩 모델 입력, 응답·대화·표시용 처리 내역에는 포함하지 않는다. Provider별 모델 API 키는 기존 방식으로 별도 사용한다.

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
