export const ROUTE_NAMES = {data_query: "위젯 생성", schema_qa: "DB 구조 설명", general_chat: "일반 대화 (DB 조회 아님)", clarify: "되묻기", other: "분류 불확실"};
export const ROUTE_SOURCE_NAMES = {jev: "TypeSafe Jev", llm_fallback: "채팅 LLM (Jev 대신 분류)", user_choice: "사용자 선택"};
export const SCHEMA_REASON_NAMES = {small_schema: "테이블 수가 적어 전체 스키마 사용", no_matched_tables: "유사 질문에 관련 테이블 없음 · 전체 스키마 사용"};

export const LOOP_STOP_NAMES = {
  done: "목표 충족", clarify: "사용자 경로 확인 대기", incomplete: "미완료",
  no_progress: "같은 작업 반복으로 중단", budget: "시간 또는 단계 한도 도달",
};
export const VERDICT_NAMES = {next: "다음 단계", done: "완료", pause: "사용자 확인 대기", replan: "재계획", incomplete: "미완료"};
export const ACTION_NAMES = {generate_sql: "SQL 생성", execute_sql: "SQL 실행", select_widgets: "위젯 선택", create_widget: "위젯 생성", evaluate: "목표 평가"};
export const ACTION_STATUS_NAMES = {ok: "완료", error: "실패", incomplete: "미완료"};

/** Keep every recorded step in order, including returns to an earlier route. */
export function routeSummary(meta) {
  const steps = meta?.steps || [];
  if (!steps.length) return ROUTE_NAMES[meta?.route] || meta?.route || "경로 미기록";
  const routes = steps.map((step) => step.route);
  // Older traces can omit a final clarification step; never infer missing execution routes.
  if (meta.route === "clarify" && routes.at(-1) !== "clarify") routes.push("clarify");
  const label = (route) => ROUTE_NAMES[route] || route || "경로 미기록";
  return routes.map((route, index) => routes.length > 1 ? `${index + 1}. ${label(route)}` : label(route)).join(" → ");
}

/** Old traces omit queries. Match the original plan only when no replan replaced it. */
export function stepQuestion(meta, step, index) {
  if (typeof step.query === "string" && step.query.trim()) return step.query.trim();
  if (meta?.replans || meta?.plan?.replans) return null;
  const planned = meta?.plan?.steps?.[index];
  if (!planned || planned.route !== (step.expected_route || step.route)) return null;
  return typeof planned.query === "string" && planned.query.trim() ? planned.query.trim() : null;
}
