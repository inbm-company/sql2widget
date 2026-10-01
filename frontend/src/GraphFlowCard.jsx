import { useEffect, useRef } from "react";
import { mutate as swrMutate } from "swr";
import { api } from "./api";
import { storeKeys, useSWR } from "./store";

function SchemaSummary({ schema }) {
  if (!schema) return null;
  return (
    <div className="graph-flow-schema">
      <div className="graph-flow-types">
        {schema.entity_types.map((type) => (
          <div key={type.name} className="graph-flow-type">
            <strong>{type.name}</strong>
            {type.description ? <span className="muted small"> — {type.description}</span> : null}
            {type.examples.length ? <div className="muted small">예: {type.examples.join(", ")}</div> : null}
            {type.properties.length ? <div className="muted small">속성: {type.properties.join(", ")}</div> : null}
          </div>
        ))}
      </div>
      {schema.relation_types.length ? (
        <ul className="graph-flow-relations">
          {schema.relation_types.map((rel) => (
            <li key={`${rel.name}:${rel.from}:${rel.to}`} className="small">
              {rel.from} <span className="muted">—{rel.name}→</span> {rel.to}
              {rel.description ? <span className="muted"> · {rel.description}</span> : null}
            </li>
          ))}
        </ul>
      ) : null}
      {schema.questions.length ? (
        <div className="graph-flow-questions small">
          <strong>확인이 필요해요</strong>
          <ul>{schema.questions.map((question) => <li key={question}>{question}</li>)}</ul>
        </div>
      ) : null}
    </div>
  );
}

function ExtractStatus({ source }) {
  const progress = source.extract_progress || { done: 0, total: 0, failed: 0 };
  if (source.extract_status === "running") {
    const percent = progress.total ? Math.round((progress.done / progress.total) * 100) : 0;
    return (
      <div className="graph-flow-status" role="status">
        <div className="small">엔티티 추출 중 · 조각 {progress.done}/{progress.total}{progress.failed ? ` · 실패 ${progress.failed}` : ""}</div>
        <progress max="100" value={percent} aria-label="추출 진행률" />
      </div>
    );
  }
  if (source.extract_status === "completed") {
    return (
      <div className="graph-flow-status" role="status">
        <div className="small">
          추출 완료 · 엔티티 {source.entity_count}개 · 관계 {source.relation_count}개
          {progress.failed ? ` · 실패한 조각 ${progress.failed}개` : ""} · Stage의 ‘그래프’ 보기 → ‘엔티티’에서 확인하세요.
        </div>
      </div>
    );
  }
  if (source.extract_status === "failed") {
    return <div className="graph-flow-status" role="alert"><div className="small">추출 실패: {source.extract_error}</div></div>;
  }
  return null;
}

export default function GraphFlowCard({ graph, projectId }) {
  const { data } = useSWR(
    storeKeys.graphSources(projectId),
    () => api.listGraphSources(projectId),
    { refreshInterval: (latest) => (latest?.sources?.some((s) => s.extract_status === "running") ? 2000 : 0) }
  );
  const source = data?.sources?.find((item) => item.id === graph.source_id);
  const previous = useRef(source?.extract_status);
  useEffect(() => {
    if (previous.current === "running" && source?.extract_status === "completed") {
      swrMutate(storeKeys.projectEntities(projectId));
      swrMutate(storeKeys.projectGraph(projectId));
    }
    previous.current = source?.extract_status;
  }, [source?.extract_status, projectId]);
  return (
    <div className="graph-flow-card">
      <div className="graph-flow-head">
        <strong>{graph.source_name}</strong>
        <span className="muted small">스키마 {({ none: "없음", proposed: "제안됨", approved: "승인됨" })[source?.schema_status || graph.schema_status]}</span>
      </div>
      <SchemaSummary schema={graph.schema} />
      {source ? <ExtractStatus source={source} /> : null}
    </div>
  );
}
