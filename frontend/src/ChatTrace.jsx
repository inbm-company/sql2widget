import { graphSummary, ROUTE_NAMES, ROUTE_SOURCE_NAMES, SCHEMA_REASON_NAMES } from "./chatTrace.js";

const retrievalNames = {
  matched: "참고자료 전달", no_match: "유사 질문 없음", unavailable: "검색 사용 불가",
  no_permissions: "허용 테이블 없음", no_connection: "DB 연결 없음",
};
const extractionNames = { running: "추출 중", completed: "추출 완료", failed: "추출 실패", pending: "대기", cancelled: "취소" };

export default function ChatTrace({ meta }) {
  if (!meta || !Object.keys(meta).length) {
    return <p className="chat-trace-empty">처리 내역 · 기록 없음 (이 답변의 사용 경로는 확인할 수 없습니다)</p>;
  }
  const knowledge = meta.knowledge;
  const schema = meta.schema_link;
  const retrieval = meta.question_retrieval;
  const build = meta.graph_build;
  return (
    <details className="chat-trace">
      <summary>처리 내역 · {ROUTE_NAMES[meta.route] || "경로 미기록"} · {graphSummary(meta)}</summary>
      <div className="chat-trace-body">
        <dl className="chat-trace-facts">
          <dt>선택 경로</dt><dd>{ROUTE_NAMES[meta.route] || "미기록"}</dd>
          <dt>분류 방식</dt><dd>{ROUTE_SOURCE_NAMES[meta.route_source] || "미기록"}
            {Number.isFinite(meta.route_confidence) ? ` · 확신 ${(meta.route_confidence * 100).toFixed(1)}%` : ""}
          </dd>
          {meta.route_candidate ? <><dt>분류 후보</dt><dd>{ROUTE_NAMES[meta.route_candidate] || "미기록"} · 확정하지 않고 되묻기</dd></> : null}
          {meta.model ? <><dt>답변 모델</dt><dd>{meta.provider} · {meta.model}</dd></> : null}
          <dt>지식그래프</dt><dd>{graphSummary(meta)}</dd>
          {knowledge && Number.isFinite(knowledge.entities_total) ? <>
            <dt>그래프 전체</dt><dd>엔티티 {knowledge.entities_total}개 · 관계 {knowledge.relations_total ?? knowledge.relations_read ?? 0}개</dd>
            <dt>조회 결과</dt><dd>엔티티 {knowledge.entities_read ?? knowledge.entities_total}개 · 관계 {knowledge.relations_read ?? 0}개
              {knowledge.truncated ? " · 조회 한도에 도달해 일부 결과만 읽음" : ""}</dd>
            <dt>답변 모델에 전달</dt><dd>엔티티 {knowledge.entities_in_prompt ?? 0}개 · 관계 {knowledge.relations_in_prompt ?? 0}개</dd>
            <dt>모델이 사용했다고 보고</dt><dd>엔티티 {knowledge.used_entities?.length ?? knowledge.used?.length ?? 0}개</dd>
          </> : null}
          {schema ? <><dt>SQL 테이블 선택</dt><dd>
            {schema.source === "graph" ? "문서 그래프의 테이블 설명" : schema.source === "similarity" ? "유사 예상 질문의 SQL" : "전체 스키마"}
            {schema.reason ? ` · ${SCHEMA_REASON_NAMES[schema.reason] || schema.reason}` : ""}
            {schema.escalated_to_full ? " · 실행 실패 후 전체 스키마로 재시도" : ""}
          </dd>
            {Number.isFinite(schema.documented_tables) ? <><dt>그래프 테이블 설명</dt><dd>허용 테이블과 대응되는 설명 {schema.documented_tables}개</dd></> : null}
            {schema.tables?.length ? <><dt>처음 선택한 테이블</dt><dd>{schema.tables.join(", ")}</dd></> : null}
          </> : null}
          {retrieval ? <><dt>예상 질문 검색</dt><dd>{retrievalNames[retrieval.status] || "미기록"} · {retrieval.count ?? 0}개</dd></> : null}
          {build ? <><dt>그래프 구성 소스</dt><dd>{build.source_name}</dd><dt>응답 당시 상태</dt><dd>
            {extractionNames[build.extract_status] || build.extract_status || "추출 전"} · 엔티티 {build.entity_count}개 · 관계 {build.relation_count}개
          </dd></> : null}
          {meta.retried ? <><dt>SQL 복구</dt><dd>1회 재시도 후 성공</dd></> : null}
        </dl>
        {knowledge?.prompt_entities?.length ? <details className="chat-trace-list">
          <summary>답변 모델에 전달한 엔티티 {knowledge.prompt_entities.length}개</summary>
          <ul>{knowledge.prompt_entities.map((entity) => <li key={entity.id}>{entity.type} · {entity.name} · {entity.source}</li>)}</ul>
        </details> : null}
        {knowledge && knowledge.entities_in_prompt > 0 ? <section>
          <h4>모델이 사용했다고 보고한 근거</h4>
          <p className="chat-trace-note">모델의 사용 보고입니다. 답변이 근거를 정확히 반영했는지는 원문과 대조할 수 있습니다.</p>
          {knowledge.used_entities?.length ? knowledge.used_entities.map((entity) => <div className="chat-trace-evidence" key={entity.id}>
            <strong>{entity.type} · {entity.name}</strong><p>{entity.source}</p>
            {(entity.evidence || []).filter((item) => item.evidence).map((item, index) => <blockquote key={index}>
              {item.heading ? <span>{item.heading}</span> : null}{item.evidence}
            </blockquote>)}
          </div>) : <p className="chat-trace-note">모델이 사용한 엔티티를 보고하지 않았습니다.</p>}
          {knowledge.used_relations?.length ? <details className="chat-trace-list">
            <summary>보고된 근거 사이의 관계 {knowledge.used_relations.length}개</summary>
            <ul>{knowledge.used_relations.map((relation, index) => <li key={index}>
              {relation.from} → {relation.type} → {relation.to}{relation.evidence ? ` · ${relation.evidence}` : ""}
            </li>)}</ul>
          </details> : null}
        </section> : null}
        {schema?.selected_descriptions?.length ? <details className="chat-trace-list">
          <summary>테이블 선택에 전달한 설명</summary>
          <ul>{schema.selected_descriptions.map((table) => <li key={table.name}>{table.name} · {table.description || "이름만 전달 (문서 설명 없음)"}</li>)}</ul>
        </details> : null}
        {retrieval?.references?.length ? <details className="chat-trace-list">
          <summary>SQL 계획에 전달한 유사 질문</summary>
          <ul>{retrieval.references.map((item, index) => <li key={index}>{item.question}
            {Number.isFinite(item.similarity) ? ` · 유사도 ${(item.similarity * 100).toFixed(1)}%` : ""}
          </li>)}</ul>
        </details> : null}
      </div>
    </details>
  );
}
