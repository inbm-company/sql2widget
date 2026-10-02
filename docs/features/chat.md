# 기능: DB 채팅

| 항목 | 내용 |
|------|------|
| 문서명 | 기능: DB 채팅 |
| 기준일 | 2026-10-02 (분리 후 구현 기준) |
| 관련 문서 | [README](../../README.md), [기능 색인](README.md) |

## DB 선택과 질문

`POST /api/chat` 입력은 `conversation_id`, `message`, 선택적 `connection_id`, `route`다. route는 `data_query` / `schema_qa`만 허용한다. 프로젝트와 대화는 로그인한 본인의 리소스만 접근한다.

- `data_query`: 허용 테이블의 실제 스키마와 예상 질문의 SQL·위젯 계획을 실 LLM에 전달하고 읽기 전용 SQL을 실행해 위젯을 생성한다.
- `schema_qa`: 현재 연결한 DB의 허용 테이블·컬럼·키 구조를 답한다.
- 의도가 불분명하면 위 두 경로의 선택지를 반환한다. TypeSafe Jev 실패 시 채팅 LLM이 판단하며, LLM도 실패하면 HTTP 502다.
- 문서 질문·그래프 구성 경로와 문서 그래프 참조는 없다. `schema_linking.py`는 큰 DB에서 유사 질문이 사용한 테이블만 전달하고, 매칭이 없으면 전체 허용 스키마를 전달한다.
- SQL/계획 실행 실패 시 전체 스키마로 한 번 수정 요청한다. 그래도 실패하면 오류를 표시한다.

## SQL과 위젯

고객 DB는 SELECT/WITH 기반 읽기 전용 조회만 허용한다. 역할별 테이블 접근 권한과 서버 위젯 화이트리스트를 검증한다. 지원 위젯은 [widgets-artifact.md](widgets-artifact.md)를 본다.

기존 SOC 데모의 고정 `DocumentProvider` 출처 보조 기능은 유지한다. 사용자 업로드 문서나 doc2graph의 그래프를 읽는 기능은 아니다.

## 저장과 AI 설정

대화 메시지·Artifact·표시용 처리 내역은 서비스 DB에 저장한다. 처리 내역에는 경로·모델·SQL 테이블 선택·유사 질문·복구 결과를 표시한다. API 키·원시 오류·참조 SQL 계획은 표시용 meta에 저장하지 않는다.

기존 메시지 임베딩 저장·검색과 `related_messages` 응답은 A에 유지한다. 예상 질문용 `question_catalog`와는 별개다. 프런트엔드는 related_messages를 아직 표시하지 않는다.

Provider별 브라우저 AI 설정은 `sql2widget_ai_settings`에 보관하고 `X-LLM-*` 헤더로 요청한다. 모델 키가 없거나 호출이 실패하면 추측 응답 대신 오류를 표시한다.
