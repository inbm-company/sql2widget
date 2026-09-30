# 기능: DB별 명령 유사도 검색

| 항목 | 내용 |
|------|------|
| 문서명 | 기능 문서 — 명령 유사도 DB |
| 기준일 | 2026-09-22 (구현 기준) |
| 관련 문서 | [chat.md](chat.md), [admin.md](admin.md) |
| 관련 코드 | `backend/app/command_similarity.py`, `backend/app/repositories/command_catalog.py`, `backend/sql/chat_vector/002_command_catalog.sql`, `backend/app/agent_service.py` |

## 1. 동작

**사용자 명령 → 선택한 DB의 명령 유사도 검색 → 검색 결과를 참조해 답변 생성**.
검색의 기준은 자연어 명령이다. SQL·위젯·DB 정보는 그 명령에 연결된 실행 정보다.
이 문서는 이전 SQL 예제 중심 설계를 사용자 요구에 맞춰 대체한다.

```text
사용자 명령: “고객별 매출 순위를 알려줘”
  → 명령 자체를 임베딩
  → 같은 고객·DB·허용 스키마·임베딩 모델의 명령 검색
  → 유사 명령 + 유사도 + SQL·위젯·DB 정보 반환
  → LLM이 검색 결과와 현재 명령·스키마를 참고해 답변 계획 생성
  → SELECT 검증 → 고객 DB에서 최신 결과 조회 → 위젯 반환
```

기본 검색 기준은 코사인 유사도 0.75 이상, 상위 5개다. 점수는 의도가 동일하다는 보증이 아니다.
LLM은 날짜·조건·집계·정렬을 현재 명령에 맞게 해석하며, 재시도에도 동일한 검색 결과가 전달된다.
검색 결과가 없으면 현재 스키마로 LLM이 계획을 생성한다. 검색 장애는 `unavailable`로 구분한다.
LLM 자체가 실패하면 기존과 같이 오류를 반환한다.

## 2. 저장 정보

기존 `chat_vector` DB에 별도 `command_catalog` 테이블을 사용한다.
채팅 로그인 `message_embeddings`와 분리되어 있다.

| 필드 | 의미 |
|------|------|
| `id`, `tenant_id`, `connection_id` | 명령 ID와 고객·DB 범위 |
| `command`, `embedding` | 자연어 명령과 그 명령의 벡터 |
| `plan` | 응답 요약, Artifact 타입, SQL·컴포넌트·제목을 포함한 위젯 목록 |
| `database_info` | 연결 ID, 표시 이름, DB 이름, 허용 테이블, 스키마 |
| `schema_hash` | 등록 당시 허용 스키마의 해시 |
| `embedding_model` | 제공자·모델·차원 식별자 |
| `command_key`, `created_at`, `updated_at` | 중복 등록 방지 키와 등록·갱신 시간 |

비밀번호·API 키·조회 결과 행은 저장하지 않는다. 명령 하나가 여러 SQL·위젯을 가질 수 있다.
같은 범위에서 공백·대소문자를 정규화한 명령을 다시 등록하면 기존 항목을 갱신한다.
다른 고객·DB·모델·스키마 항목은 검색에 포함하지 않는다.
허용 테이블이나 스키마가 바뀌면 그 범위의 명령을 다시 등록해야 한다.
권한이 없는 역할에는 기존 채팅의 데모 권한 폴백을 적용해 카탈로그를 노출하지 않는다.

## 3. 초기 등록

관리자 → AI 설정 저장 → DB 선택 → 역할별 테이블 권한 저장 → **명령 유사도 DB / 초기 명령 3개 등록**.

1. 선택한 DB에서 지정 역할의 허용 스키마를 읽는다.
2. AI가 사용자 명령과 각 명령에 연결할 SQL·위젯 계획을 생성한다.
3. 위젯 허용 목록과 SQL을 검증하고, 고객 DB에서 SELECT를 읽기 전용 실행한다.
4. 명령 문자열을 임베딩한다.
5. 명령·벡터·실행 정보·DB 정보를 하나의 트랜잭션으로 저장한다.
6. 화면에 등록된 명령을 보여주고, 펼치면 SQL·위젯 정보를 확인할 수 있다.

SQL 검증 또는 임베딩이 실패하면 해당 요청의 명령을 부분 저장하지 않는다.
자동 생성 외에 관리자가 명령과 실행 정보를 직접 전달하는 등록 API도 제공한다.
DB 연결 생성 자체에서 AI 호출을 실행하지 않으며, 초기 등록 동작을 명시적으로 실행한다.
채팅에서 발생한 모든 명령을 자동 학습·저장하지는 않는다.

## 4. API

모든 경로의 접두사는 `/api/database-connections/{connection_id}`다.
AI 설정 헤더는 채팅과 같은 `X-LLM-Provider`, `X-LLM-API-Key`, `X-LLM-Model`을 사용한다.

| Method / Path | 입력 | 권한·결과 |
|---------------|------|-----------|
| POST `/commands/seed` | `role`(기본 user), `count`(기본 3, 최대 5) | 관리자, `saved_count`와 `commands` 반환 |
| POST `/commands` | `command`, `plan`, `role` | 관리자, 검증 후 명령 한 개 등록 |
| POST `/commands/search` | `command`, `limit`(기본 5, 최대 10), `min_similarity`(기본 0.75) | 로그인 사용자 자신의 역할 기준, `status`와 `matches` 반환 |

직접 등록 본문 형태:

```json
{
  "role": "user",
  "command": "전체 주문 건수를 알려줘",
  "plan": {
    "summary": "주문 건수를 조회했습니다.",
    "artifact_type": "widget",
    "widgets": [{
      "component": "KpiStat",
      "title": "주문 건수",
      "sql": "SELECT count(*) AS value FROM orders"
    }]
  }
}
```

검색 결과에는 명령, 유사도, 연결 ID, DB 정보, 실행 계획이 포함된다.
채팅 응답에서는 `meta.command_retrieval`에 검색 상태와 결과를 담는다.
명령 검색 전용 API는 검색 장애 시 HTTP 502, 잘못된 등록 SQL은 HTTP 400,
다른 고객의 연결은 HTTP 404, 비관리자 등록은 HTTP 403을 반환한다.

## 5. 실행 및 검증 범위

```sh
docker compose exec backend python scripts/migrate_chat_vector.py
docker compose exec backend pytest -q
```

Compose 시작 시에도 벡터 DB 마이그레이션이 적용된다. 새 의존성이나 별도 DB 서버는 필요 없다.
실제 pgvector 테스트는 고객·DB·스키마·모델 분리, 유사도 순서, 임계값, 중복 갱신을 검사하고 롤백한다.
서비스 테스트는 검색 결과의 LLM 전달·재시도, 빈 검색, 장애, 초기 등록과 권한 검사를 검증한다.

현재 초기 생성은 허용 스키마 전체를 한 번에 전달한다. 대규모 스키마의 배치 생성,
자동 갱신·삭제 UI, 실제 명령 데이터로 유사도 임계값을 보정하는 작업은 포함하지 않는다.

2026-09-22 로컬 검증: 백엔드 테스트 29개와 프론트 빌드 통과. 관리자 화면에서 실제 AI로 SOC DB 초기 명령 3개를 등록했다. “공격 방식마다 몇 건씩 발생했는지 그래프로 보여줘”가 저장된 “공격 유형별 발생 건수 통계 보여줘”를 유사도 0.8978로 검색하고 Gemini 답변 계획을 거쳐 BarChart를 생성하는 흐름을 확인했다.
