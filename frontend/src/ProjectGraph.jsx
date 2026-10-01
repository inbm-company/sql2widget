import { useEffect, useId, useMemo, useRef, useState } from "react";
import { api } from "./api";
import { storeKeys, useSWR } from "./store";
import { filterGraph, layoutGraph } from "./graphLayout";
import { MIN_GRAPH_ZOOM, MAX_GRAPH_ZOOM, zoomGraph } from "./graphViewport";

export function GraphDiagram({ nodes, links, selectedId, onSelect, colorOf = null, label = "문서" }) {
  const graph = useMemo(() => layoutGraph(nodes, links), [nodes, links]);
  const center = { x: (Math.min(...graph.nodes.map((n) => n.x), graph.width / 2) + Math.max(...graph.nodes.map((n) => n.x), graph.width / 2)) / 2,
    y: (Math.min(...graph.nodes.map((n) => n.y), graph.height / 2) + Math.max(...graph.nodes.map((n) => n.y), graph.height / 2)) / 2 };
  const width = Math.max(400, Math.max(...graph.nodes.map((n) => n.x), graph.width / 2) - Math.min(...graph.nodes.map((n) => n.x), graph.width / 2) + 280);
  const height = Math.max(280, Math.max(...graph.nodes.map((n) => n.y), graph.height / 2) - Math.min(...graph.nodes.map((n) => n.y), graph.height / 2) + 120);
  const [viewport, setViewport] = useState({ zoom: 1, pan: { x: 0, y: 0 } });
  const { zoom, pan } = viewport;
  const svgRef = useRef(null);
  function graphPoint(svg, event) {
    const matrix = svg.getScreenCTM();
    return matrix ? new DOMPoint(event.clientX, event.clientY).matrixTransform(matrix.inverse()) : null;
  }
  useEffect(() => {
    const svg = svgRef.current;
    function wheel(event) {
      event.preventDefault();
      const point = graphPoint(svg, event);
      if (!point) return;
      const unit = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? svg.clientHeight : 1;
      const delta = Math.max(-100, Math.min(100, event.deltaY * unit));
      setViewport((current) => zoomGraph(current, current.zoom * Math.exp(-delta * 0.002), point, { x: center.x, y: center.y }));
    }
    svg.addEventListener("wheel", wheel, { passive: false });
    return () => svg.removeEventListener("wheel", wheel);
  }, [center.x, center.y]);
  const drag = useRef(null);
  const markerId = useId().replace(/:/g, "");
  const lookup = new Map(graph.nodes.map((node) => [node.id, node]));
  const neighbors = new Set([selectedId]);
  links.forEach((link) => {
    if (link.source === selectedId) neighbors.add(link.target);
    if (link.target === selectedId) neighbors.add(link.source);
  });
  function startPan(event) {
    if (event.button !== 0 || event.target.closest("[data-graph-node]")) return;
    const point = graphPoint(event.currentTarget, event);
    if (!point) return;
    drag.current = { point, pan };
    event.currentTarget.setPointerCapture(event.pointerId);
  }
  function movePan(event) {
    if (!drag.current) return;
    const start = drag.current;
    const point = graphPoint(event.currentTarget, event);
    if (!point) return;
    setViewport((current) => ({ ...current, pan: {
      x: start.pan.x + point.x - start.point.x,
      y: start.pan.y + point.y - start.point.y,
    } }));
  }
  return <div className="graph-diagram-wrap">
    <div className="graph-zoom">
      <button type="button" className="ghost" aria-label="그래프 축소" disabled={zoom <= MIN_GRAPH_ZOOM} onClick={() => setViewport((current) => zoomGraph(current, current.zoom / 1.3, center, center))}>−</button>
      <span className="muted small">{Math.round(zoom * 100)}%</span>
      <button type="button" className="ghost" aria-label="그래프 확대" disabled={zoom >= MAX_GRAPH_ZOOM} onClick={() => setViewport((current) => zoomGraph(current, current.zoom * 1.3, center, center))}>+</button>
      <button type="button" className="ghost" onClick={() => setViewport({ zoom: 1, pan: { x: 0, y: 0 } })}>전체 보기</button>
    </div>
    <svg ref={svgRef} className="graph-diagram" viewBox={`${center.x - width / 2} ${center.y - height / 2} ${width} ${height}`} role="group" aria-label={`프로젝트 ${label} 그래프`}
      onPointerDown={startPan} onPointerMove={movePan} onPointerUp={(event) => {
        drag.current = null;
        if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
      }} onPointerCancel={() => { drag.current = null; }} onLostPointerCapture={() => { drag.current = null; }}>
      <defs><marker id={markerId} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="currentColor" /></marker></defs>
      <g transform={`translate(${center.x + pan.x} ${center.y + pan.y}) scale(${zoom}) translate(${-center.x} ${-center.y})`}>
        {links.map((edge) => {
          const from = lookup.get(edge.source), to = lookup.get(edge.target);
          if (!from || !to) return null;
          const selected = edge.source === selectedId || edge.target === selectedId;
          if (edge.source === edge.target) return <path key={`${edge.source}:${edge.target}`} className={`graph-edge ${selected ? "selected" : ""}`} d={`M ${from.x - 7} ${from.y - 8} c -35 -45 50 -45 15 0`} markerEnd={`url(#${markerId})`} />;
          const dx = to.x - from.x, dy = to.y - from.y, distance = Math.max(1, Math.hypot(dx, dy));
          return <line key={`${edge.source}:${edge.target}`} className={`graph-edge ${selected ? "selected" : ""}`} x1={from.x + dx / distance * 13} y1={from.y + dy / distance * 13} x2={to.x - dx / distance * 16} y2={to.y - dy / distance * 16} markerEnd={`url(#${markerId})`} />;
        })}
        {graph.nodes.map((node) => <g key={node.id} data-graph-node={node.id} className={`graph-node ${selectedId === node.id ? "selected" : ""} ${selectedId && !neighbors.has(node.id) ? "dimmed" : ""}`}
          transform={`translate(${node.x} ${node.y})`} role="button" tabIndex={0} aria-label={`${label} ${node.title}`} aria-pressed={selectedId === node.id}
          onClick={() => onSelect(node.id)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onSelect(node.id); } }}>
          <title>{`${node.title}\n${node.path}`}</title><circle r="12" style={colorOf && selectedId !== node.id ? { fill: colorOf(node), stroke: colorOf(node) } : undefined} /><text y="29" textAnchor="middle">{node.title.length > 20 ? `${node.title.slice(0, 20)}…` : node.title}</text>
        </g>)}
      </g>
    </svg>
    <p className="muted small graph-hint">노드: {label} · 화살표: {label === "문서" ? "문서 링크" : "관계"} · 휠로 확대·축소하고 배경을 드래그해 이동하세요.</p>
  </div>;
}

function DocumentGraph({ projectId }) {
  const { data, error, isLoading, isValidating, mutate } = useSWR(storeKeys.projectGraph(projectId), () => api.getProjectGraph(projectId));
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const { data: document, error: documentError, isLoading: documentLoading, mutate: refreshDocument } = useSWR(
    storeKeys.graphDocument(projectId, selectedId), () => api.getGraphDocument(projectId, selectedId)
  );
  useEffect(() => { if (selectedId) refreshDocument(); }, [data, selectedId, refreshDocument]);
  const filtered = useMemo(() => data ? filterGraph(data, query) : { nodes: [], links: [] }, [data, query]);
  const selectedNode = filtered.nodes.find((node) => node.id === selectedId);
  useEffect(() => { if (selectedId && !selectedNode) setSelectedId(null); }, [selectedId, selectedNode]);
  const related = selectedNode ? filtered.links.filter((link) => link.source === selectedId || link.target === selectedId) : [];
  const neighbors = [...new Set(related.map((link) => link.source === selectedId ? link.target : link.source))];
  return <div>
    <div className="graph-toolbar">
      <input type="search" aria-label="그래프 문서 검색" placeholder="문서 제목 또는 경로 검색" value={query} onChange={(event) => setQuery(event.target.value)} />
      <button type="button" className="ghost" disabled={isValidating} onClick={() => mutate()}>{isValidating ? "불러오는 중…" : "새로고침"}</button>
    </div>
    {data ? <p className="muted small">소스 {data.totals.source_count}개 · 문서 {data.totals.document_count}개 · 본문 조각 {data.totals.chunk_count}개 · 링크 {data.totals.link_count}개</p> : null}
    {isLoading ? <p className="muted" role="status">그래프를 불러오고 있습니다…</p> : null}
    {error ? <p className="admin-status" role="alert">{error.message}</p> : null}
    {data?.truncated ? <p className="graph-limit small" role="status">전체 중 문서 최대 {data.node_limit}개, 링크 최대 {data.link_limit}개를 표시합니다. 검색은 표시된 문서를 대상으로 합니다.</p> : null}
    {data && !data.nodes.length ? <div className="graph-empty"><strong>아직 적재된 문서가 없습니다.</strong><p className="muted small">DB 관리에서 이 프로젝트에 경로를 등록하거나 기존 소스를 연결한 뒤 ‘적재’를 실행하세요.</p></div> : null}
    {data?.nodes.length && !filtered.nodes.length ? <p className="muted small">검색한 문서가 없습니다.</p> : null}
    {filtered.nodes.length ? <GraphDiagram nodes={filtered.nodes} links={filtered.links} selectedId={selectedId} onSelect={setSelectedId} /> : null}
    {selectedNode ? <div className="graph-document">
      <h3>{selectedNode.title}</h3><p className="muted small">{selectedNode.source_name} · 본문 조각 {selectedNode.chunk_count}개</p><p className="graph-source-path small">{selectedNode.path}</p>
      {neighbors.length ? <div className="graph-neighbors"><span className="muted small">연결된 문서</span>{neighbors.map((id) => <button type="button" className="ghost" key={id} onClick={() => setSelectedId(id)}>{filtered.nodes.find((node) => node.id === id)?.title}</button>)}</div> : null}
      {documentLoading ? <p role="status" className="muted small">본문을 불러오는 중…</p> : null}
      {documentError ? <p role="alert" className="admin-status">{documentError.message}</p> : null}
      {document ? <><pre className="graph-document-content">{document.content}</pre>{document.content_truncated ? <p className="muted small">본문은 처음 100,000자까지 표시합니다.</p> : null}</> : null}
    </div> : filtered.nodes.length ? <p className="muted small">문서 노드를 선택하면 본문과 연결된 문서를 확인할 수 있습니다.</p> : null}
  </div>;
}

const TYPE_COLORS = ["#4e79a7", "#f28e2b", "#59a14f", "#e15759", "#b07aa1", "#76b7b2", "#edc948", "#9c755f"];

function EntityGraph({ projectId }) {
  const { data, error, isLoading, isValidating, mutate } = useSWR(storeKeys.projectEntities(projectId), () => api.getProjectEntities(projectId));
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const types = useMemo(() => [...new Set((data?.entities || []).map((entity) => entity.type))].sort(), [data]);
  const colorOf = (node) => TYPE_COLORS[types.indexOf(node.path) % TYPE_COLORS.length];
  const counts = useMemo(() => Object.fromEntries(types.map((type) => [type, (data?.entities || []).filter((e) => e.type === type).length])), [data, types]);
  const graph = useMemo(() => {
    const search = query.trim().toLocaleLowerCase();
    const nodes = (data?.entities || []).filter((e) => !search || `${e.name} ${e.type}`.toLocaleLowerCase().includes(search))
      .map((e) => ({ id: e.id, title: e.name, path: e.type }));
    const ids = new Set(nodes.map((node) => node.id));
    return { nodes, links: (data?.relations || []).filter((r) => ids.has(r.source) && ids.has(r.target)) };
  }, [data, query]);
  const entity = (data?.entities || []).find((item) => item.id === selectedId);
  useEffect(() => { if (selectedId && !graph.nodes.some((node) => node.id === selectedId)) setSelectedId(null); }, [selectedId, graph]);
  const names = new Map((data?.entities || []).map((item) => [item.id, item.name]));
  const related = entity ? (data.relations || []).filter((rel) => rel.source === entity.id || rel.target === entity.id) : [];
  const properties = entity?.properties && typeof entity.properties === "object" ? entity.properties : {};
  return <div>
    <div className="graph-toolbar">
      <input type="search" aria-label="엔티티 검색" placeholder="엔티티 이름 또는 타입 검색" value={query} onChange={(event) => setQuery(event.target.value)} />
      <button type="button" className="ghost" disabled={isValidating} onClick={() => mutate()}>{isValidating ? "불러오는 중…" : "새로고침"}</button>
    </div>
    {data ? <p className="muted small">엔티티 {data.entities.length}개 · 관계 {data.relations.length}개</p> : null}
    {types.length ? <div className="graph-legend" aria-label="엔티티 타입 범례">
      {types.map((type) => <span key={type} className="graph-legend-item small"><i style={{ background: colorOf({ path: type }) }} />{type} {counts[type]}</span>)}
    </div> : null}
    {isLoading ? <p className="muted" role="status">엔티티를 불러오고 있습니다…</p> : null}
    {error ? <p className="admin-status" role="alert">{error.message}</p> : null}
    {data && !data.entities.length ? <div className="graph-empty"><strong>아직 추출된 엔티티가 없습니다.</strong><p className="muted small">채팅에서 “문서를 그래프로 만들어줘”라고 요청해 스키마를 정하고 추출하세요.</p></div> : null}
    {data?.truncated ? <p className="graph-limit small" role="status">엔티티가 많아 일부만 표시합니다.</p> : null}
    {data?.entities.length && !graph.nodes.length ? <p className="muted small">검색한 엔티티가 없습니다.</p> : null}
    {graph.nodes.length ? <GraphDiagram nodes={graph.nodes} links={graph.links} selectedId={selectedId} onSelect={setSelectedId} colorOf={colorOf} label="엔티티" /> : null}
    {entity ? <div className="graph-document">
      <h3>{entity.name}</h3>
      <p className="muted small">타입 {entity.type}</p>
      {Object.keys(properties).length ? <dl className="graph-props small">{Object.entries(properties).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{String(value)}</dd></div>)}</dl> : null}
      {related.length ? <div className="graph-neighbors"><span className="muted small">관계</span>{related.map((rel) => {
        const out = rel.source === entity.id, other = out ? rel.target : rel.source;
        return <button type="button" className="ghost" key={`${rel.type}:${rel.source}:${rel.target}`} title={rel.evidence} onClick={() => setSelectedId(other)}>{out ? `${rel.type} → ` : `← ${rel.type} `}{names.get(other)}</button>;
      })}</div> : null}
      {entity.evidence?.filter((item) => item.evidence).length ? <div className="graph-evidence small"><span className="muted">원문 근거</span>
        {entity.evidence.filter((item) => item.evidence).map((item, index) => <blockquote key={index}>{item.evidence}{item.heading ? <cite> — {item.heading}</cite> : null}</blockquote>)}
      </div> : null}
    </div> : graph.nodes.length ? <p className="muted small">엔티티 노드를 선택하면 속성·관계·원문 근거를 확인할 수 있습니다.</p> : null}
  </div>;
}

export default function ProjectGraph({ projectId }) {
  const [mode, setMode] = useState("documents");
  return <section className="project-graph" aria-label="Stage 그래프">
    <div className="segmented graph-mode" role="group" aria-label="그래프 종류">
      <button type="button" className={mode === "documents" ? "active" : ""} onClick={() => setMode("documents")}>문서</button>
      <button type="button" className={mode === "entities" ? "active" : ""} onClick={() => setMode("entities")}>엔티티</button>
    </div>
    {mode === "documents" ? <DocumentGraph projectId={projectId} /> : <EntityGraph projectId={projectId} />}
  </section>;
}
