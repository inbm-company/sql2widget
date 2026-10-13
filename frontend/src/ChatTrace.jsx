import { LOOP_STOP_NAMES, ROUTE_NAMES, ROUTE_SOURCE_NAMES, SCHEMA_REASON_NAMES, VERDICT_NAMES } from "./chatTrace.js";
export default function ChatTrace({ meta }) {
  if (!meta || !Object.keys(meta).length) return <p className="chat-trace-empty">처리 내역 · 기록 없음</p>;
  const schema = meta.schema_link;
  const retrieval = meta.question_retrieval;
  return <details className="chat-trace"><summary>처리 내역 · {ROUTE_NAMES[meta.route] || "미기록"}</summary>
    <div className="chat-trace-body"><dl className="chat-trace-facts">
      <dt>선택 경로</dt><dd>{ROUTE_NAMES[meta.route] || "미기록"}</dd>
      <dt>분류 방식</dt><dd>{ROUTE_SOURCE_NAMES[meta.route_source] || "미기록"}</dd>
      {meta.plan?.goal ? <><dt>계획 목표</dt><dd>{meta.plan.goal}</dd></> : null}
      {meta.steps?.length ? <><dt>실행 단계</dt><dd>{meta.steps.map((step, index) => <div key={index}>
        {index + 1}. {ROUTE_NAMES[step.route] || ROUTE_NAMES[step.expected_route] || "처리 실패"}
        {step.expected_route && step.route && step.expected_route !== step.route ? ` (예상 ${ROUTE_NAMES[step.expected_route] || step.expected_route})` : ""}
        {` → ${VERDICT_NAMES[step.verdict] || step.verdict || "미기록"}`}
        {step.reason ? <span> · {step.reason}</span> : null}
        {step.widget_selection ? <div>위젯 선택: {step.widget_selection.components?.join(", ")}</div> : null}
        {step.sql_generation ? <div>SQL 생성: {step.sql_generation.count}개{step.sql_generation.repaired ? " · SQL 수정 후 성공" : ""}</div> : null}
      </div>)}</dd></> : null}
      {meta.loop_stop ? <><dt>종료</dt><dd>{LOOP_STOP_NAMES[meta.loop_stop] || meta.loop_stop}{meta.replans ? ` · 재계획 ${meta.replans}회` : ""}</dd></> : null}
      {meta.model ? <><dt>답변 모델</dt><dd>{meta.provider} · {meta.model}</dd></> : null}
      {schema ? <><dt>SQL 테이블 선택</dt><dd>{schema.source === "similarity" ? "유사 예상 질문의 SQL" : "전체 스키마"}{schema.reason ? ` · ${SCHEMA_REASON_NAMES[schema.reason] || schema.reason}` : ""}{schema.escalated_to_full ? " · 전체 스키마로 재시도" : ""}</dd>{schema.tables?.length ? <><dt>선택 테이블</dt><dd>{schema.tables.join(", ")}</dd></> : null}</> : null}
      {retrieval ? <><dt>예상 질문 검색</dt><dd>{retrieval.count || 0}개 · {retrieval.status}</dd></> : null}
      {meta.retried ? <><dt>SQL 복구</dt><dd>1회 재시도 후 성공</dd></> : null}
    </dl>{retrieval?.references?.length ? <ul>{retrieval.references.map((q,i) => <li key={i}>{q.question} · {q.similarity}</li>)}</ul> : null}</div>
  </details>;
}
