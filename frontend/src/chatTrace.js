export const ROUTE_NAMES = {
  data_query: "데이터 조회", schema_qa: "DB 구조 설명", knowledge_qa: "문서 기반 답변",
  graph_build: "지식그래프 구성", clarify: "되묻기", other: "분류 불확실",
};

export const ROUTE_SOURCE_NAMES = {
  jev: "TypeSafe Jev", llm_fallback: "채팅 LLM (Jev 대신 분류)", user_choice: "사용자 선택",
};

export const SCHEMA_REASON_NAMES = {
  small_schema: "테이블 수가 적어 전체 스키마 사용", no_project: "연결된 프로젝트 없음",
  graph_unavailable: "그래프 조회 실패 · 전체 스키마 사용",
  no_documented_tables: "그래프에 대응되는 테이블 설명 없음 · 전체 스키마 사용",
  no_tables_picked: "관련 테이블을 선택하지 못함 · 전체 스키마 사용",
  no_matched_tables: "유사 질문에 관련 테이블 없음 · 전체 스키마 사용",
};

export function graphSummary(meta) {
  if (!meta || !Object.keys(meta).length) return "기록 없음";
  const knowledge = meta.knowledge;
  if (knowledge) {
    if (knowledge.status === "no_project") return "지식그래프 조회 안 함 · 프로젝트 없음";
    if (knowledge.entities_total === 0) return "지식그래프 조회 성공 · 결과 0개";
    if (knowledge.entities_in_prompt > 0) return `지식그래프 사용 · 엔티티 ${knowledge.entities_in_prompt}개 전달`;
    return "지식그래프 조회 성공 · 답변에 전달한 근거 없음";
  }
  const schema = meta.schema_link;
  if (schema?.source === "graph") {
    return schema.escalated_to_full ? "그래프로 테이블 선택 · 전체 스키마로 재시도" : "지식그래프로 테이블 선택";
  }
  if (schema?.reason === "graph_unavailable") return "지식그래프 조회 실패 · 전체 스키마 사용";
  if (["no_documented_tables", "no_tables_picked"].includes(schema?.reason)) return "지식그래프 조회함 · 선택에 미사용";
  if (meta.route === "graph_build") return "지식그래프 구성 경로";
  return "지식그래프 조회 안 함";
}
