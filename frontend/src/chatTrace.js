export const ROUTE_NAMES = {data_query: "데이터 조회", schema_qa: "DB 구조 설명", general_chat: "일반 대화 (DB 조회 아님)", clarify: "되묻기", other: "분류 불확실"};
export const ROUTE_SOURCE_NAMES = {jev: "TypeSafe Jev", llm_fallback: "채팅 LLM (Jev 대신 분류)", user_choice: "사용자 선택"};
export const SCHEMA_REASON_NAMES = {small_schema: "테이블 수가 적어 전체 스키마 사용", no_matched_tables: "유사 질문에 관련 테이블 없음 · 전체 스키마 사용"};

export const LOOP_STOP_NAMES = {
  done: "목표 충족", clarify: "사용자 경로 확인 대기", incomplete: "미완료",
  no_progress: "같은 작업 반복으로 중단", budget: "시간 또는 단계 한도 도달",
};
export const VERDICT_NAMES = {next: "다음 단계", done: "완료", pause: "사용자 확인 대기", replan: "재계획", incomplete: "미완료"};
