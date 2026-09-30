# 기능: DB별 예상 질문 유사도 검색

| 항목 | 내용 |
|------|------|
| 문서명 | 기능 문서 — 예상 질문 유사도 DB |
| 기준일 | 2026-09-22 (구현 기준) |
| 관련 문서 | [chat.md](chat.md), [admin.md](admin.md) |
| 관련 코드 | `backend/app/question_similarity.py`, `backend/app/repositories/question_catalog.py`, `backend/app/agent_service.py` |

## 동작

사용자 질문 → 선택한 DB의 예상 질문 검색 → 검색된 질문에 연결된 SQL·위젯 정보를 참고해
LLM이 **현재 질문**에 맞는 답변 계획 생성 → 고객 DB 조회 → 위젯 반환.
검색의 기준은 자연어 질문이다. SQL, 위젯, DB 정보는 각 예상 질문에 연결된 실행 정보다.

유사도 기준은 코사인 유사도 0.75 이상, 기본 상위 5개다. 점수가 높아도 질문이 동일하다는
보장은 없으므로 LLM이 조건·날짜·집계·정렬을 현재 질문과 스키마에 맞춰 재검토한다.
검색 결과가 없거나 검색에 실패하면 LLM이 현재 스키마로 계획을 생성한다.
LLM 호출 자체가 실패하면 기존 채팅처럼 오류를 반환한다.

## 저장 구조와 접근 범위

기존 `chat_vector` DB의 `question_catalog` 테이블을 사용한다. 채팅 로그용
`message_embeddings`와 별도다. `003_question_catalog.sql`은 기존 `command_catalog`
테이블과 컬럼을 이름만 바꿔 데이터를 보존한다.

각 항목에는 `tenant_id`, `connection_id`, 자연어 `question`, 그 질문의 임베딩,
`plan`(SQL·위젯 컴포넌트·제목), DB 이름·테이블 목록, 전체 DB 스키마 해시,
임베딩 모델 식별자와 등록 시각이 저장된다. 비밀번호·API 키·조회 결과 행은 저장하지 않는다.
동일 고객·DB·스키마·모델에서 같은 질문을 다시 등록하면 기존 항목을 갱신한다.

**예상 질문 등록은 역할별로 나누지 않는다.** 선택한 DB의 전체 조회 가능 테이블을 대상으로
한 번 생성한다. 채팅에서 검색할 때는 현재 로그인 사용자의 기존 테이블 접근 권한으로
SQL 참조를 다시 검사한다. 다른 고객·DB의 질문은 검색되지 않는다.
스키마가 바뀌면 새 스키마 기준으로 다시 생성해야 한다.

## 전체 DB의 예상 질문 생성

관리자 화면에서 AI 연결 설정을 저장하고 DB를 선택한 다음 **예상 질문 생성**을 누른다.
`테이블 권한 기준` 선택과 생성 개수 입력은 없다. DB 연결을 등록할 때 자동 실행되지는 않는다.

1. DB의 조회 가능한 사용자 테이블·뷰와 컬럼·PK/FK를 읽는다. 내부 `schema_migrations`는 제외한다.
2. 4개 테이블씩 AI에 스키마를 전달해 예상 질문과 SQL·위젯을 생성한다. 코드에서
   건수·목록 같은 질문을 미리 만들거나 질문 개수를 고정하지 않는다. AI에는 각 테이블과
   집계·순위·분포·추이·필터·관계 등 서로 다른 질문 의도를 다루도록 요청한다.
3. 생성된 SQL을 현재 고객 DB에서 읽기 전용으로 검증한다. 실행할 수 없는 질문은 건너뛰고
   `skipped_count`로 알린다. 질문을 만들지 못한 테이블은 `uncovered_tables`에 표시한다.
   다른 질문 의도를 AI에 추가 요청하고, 빠진 테이블은 다시 요청한다. 유효한 AI 질문만
   묶음으로 임베딩해 저장한다.
4. 화면에 테이블 진행률과 등록된 질문 수를 보여준다. 중단되면 같은 DB에서 다시 눌러 이어간다.

조건·날짜·값의 조합은 무한하므로 가능한 모든 문장을 미리 저장할 수는 없다.
이 로직은 **조회 가능한 모든 테이블을 처리하고, 스키마로 의미가 있는 다양한 질문을 추가**한다.
저장된 질문과 가까운 새 질문은 LLM이 현재 조건에 맞게 답변을 만든다.

## API

접두사: `/api/database-connections/{connection_id}`. AI 설정 헤더는 채팅과 같은
`X-LLM-Provider`, `X-LLM-API-Key`, `X-LLM-Model`을 사용한다.

| Method / Path | 입력 | 결과 |
|---------------|------|------|
| POST `/questions/seed` | `offset`(기본 0) | 관리자 전용. `questions`, `saved_count`, `skipped_count`, `uncovered_tables`, `processed_tables`, `total_tables`, `next_offset` 반환. `next_offset`이 없을 때까지 반복 |
| POST `/questions/search` | `question`, `limit`(기본 5), `min_similarity`(기본 0.75) | 로그인 사용자의 접근 가능 SQL만 `matches`로 반환 |

채팅 응답은 `meta.question_retrieval`에 검색 상태를 포함한다.
검색 장애는 전용 API에서 HTTP 502, 생성 실패는 HTTP 502,
다른 고객의 DB는 HTTP 404, 비관리자 등록은 HTTP 403이다.

## 검증

```sh
docker compose exec backend python scripts/migrate_chat_vector.py
docker compose exec backend pytest -q
```

실제 pgvector 테스트는 고객·DB·스키마·모델 분리, 임계값과 중복 등록을 롤백하며 검증한다.
서비스 테스트는 전 테이블 처리, AI 질문 검증, 권한 밖 SQL 제외와 LLM 전달을 확인한다.
