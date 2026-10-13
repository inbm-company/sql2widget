import { ACTION_NAMES, ACTION_STATUS_NAMES, LOOP_STOP_NAMES, ROUTE_NAMES, ROUTE_SOURCE_NAMES, SCHEMA_REASON_NAMES, VERDICT_NAMES } from "./chatTrace.js";

function ToolAction({ action }) {
  const detail = action.action === "generate_sql"
    ? `${action.count ?? 0}개${action.query_ids?.length ? ` · ${action.query_ids.join(", ")}` : ""}${action.repaired ? " · SQL 수정" : ""}`
    : action.action === "execute_sql"
      ? `${action.query_id || ""}${action.row_count != null ? ` · ${action.row_count}행 · ${action.columns?.join(", ") || "컬럼 없음"}` : ""}`
      : action.action === "select_widgets"
        ? `${action.query_id || ""} · ${action.count ?? 0}개${action.components?.length ? ` · ${action.components.join(", ")}` : ""}`
        : action.action === "create_widget"
          ? `${action.widget_id || ""} · ${action.component || ""}${action.title ? ` · ${action.title}` : ""} · ${action.query_id || ""}`
          : VERDICT_NAMES[action.verdict] || "";
  return <div>
    {action.call ? `호출 ${action.call}. ` : ""}{ACTION_NAMES[action.action] || action.action}
    {` → ${ACTION_STATUS_NAMES[action.status] || action.status || "미기록"}`}
    {detail ? ` · ${detail}` : ""}
    {action.reason ? <div>{action.reason}</div> : null}
  </div>;
}
export default function ChatTrace({ meta }) {
  if (!meta || !Object.keys(meta).length) return <p className="chat-trace-empty">처리 내역 · 기록 없음</p>;
  const schema = meta.schema_link;
  const retrieval = meta.question_retrieval;
  return <details className="chat-trace"><summary>처리 내역 · {ROUTE_NAMES[meta.route] || "미기록"}</summary>
    <div className="chat-trace-body"><dl className="chat-trace-facts">
      <dt>선택 경로</dt><dd>{ROUTE_NAMES[meta.route] || "미기록"}</dd>
      <dt>분류 방식</dt><dd>{ROUTE_SOURCE_NAMES[meta.route_source] || "미기록"}</dd>
      {meta.plan?.goal ? <><dt>계획 목표</dt><dd>{meta.plan.goal}</dd></> : null}
      {meta.tool_calls != null && meta.widget_creation ? <><dt>데이터 작업 호출</dt><dd>{meta.tool_calls}회 · 다음 작업 판단 {meta.decision_calls || 0}회</dd></> : null}
      {meta.widget_creation ? <><dt>생성 결과</dt><dd>SQL {meta.sql_generation?.count || 0}개 · 위젯 {meta.widget_creation.count}개</dd></> : null}
      {meta.steps?.length ? <><dt>실행 단계</dt><dd>{meta.steps.map((step, index) => <div key={index}>
        {index + 1}. {ROUTE_NAMES[step.route] || ROUTE_NAMES[step.expected_route] || "처리 실패"}
        {step.expected_route && step.route && step.expected_route !== step.route ? ` (예상 ${ROUTE_NAMES[step.expected_route] || step.expected_route})` : ""}
        {` → ${VERDICT_NAMES[step.verdict] || step.verdict || "미기록"}`}
        {step.reason ? <span> · {step.reason}</span> : null}
        {step.actions?.length ? step.actions.map((action, actionIndex) => <ToolAction key={actionIndex} action={action} />) : <>
          {step.sql_generation ? <div>SQL 생성: {step.sql_generation.count}개{step.sql_generation.repaired ? " · SQL 수정 이력 있음" : ""}</div> : null}
          {step.widget_selection ? <div>위젯 선택: {step.widget_selection.components?.join(", ")}</div> : null}
        </>}
      </div>)}</dd></> : null}
      {meta.loop_stop ? <><dt>종료</dt><dd>{LOOP_STOP_NAMES[meta.loop_stop] || meta.loop_stop}{meta.replans ? ` · 재계획 ${meta.replans}회` : ""}</dd></> : null}
      {meta.model ? <><dt>답변 모델</dt><dd>{meta.provider} · {meta.model}</dd></> : null}
      {schema ? <><dt>SQL 테이블 선택</dt><dd>{schema.source === "similarity" ? "유사 예상 질문의 SQL" : "전체 스키마"}{schema.reason ? ` · ${SCHEMA_REASON_NAMES[schema.reason] || schema.reason}` : ""}{schema.escalated_to_full ? " · 전체 스키마로 재시도" : ""}</dd>{schema.tables?.length ? <><dt>선택 테이블</dt><dd>{schema.tables.join(", ")}</dd></> : null}</> : null}
      {retrieval ? <><dt>예상 질문 검색</dt><dd>{retrieval.count || 0}개 · {retrieval.status}</dd></> : null}
      {meta.retried ? <><dt>SQL 복구</dt><dd>{meta.sql_generation?.repairs ?? 1}회 SQL 수정</dd></> : null}
    </dl>{retrieval?.references?.length ? <ul>{retrieval.references.map((q,i) => <li key={i}>{q.question} · {q.similarity}</li>)}</ul> : null}</div>
  </details>;
}
