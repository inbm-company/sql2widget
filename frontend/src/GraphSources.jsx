import { useEffect, useState } from "react";
import { mutate as swrMutate } from "swr";
import { api } from "./api";
import { storeKeys, useSWR } from "./store";

const statusLabels = {
  registered: "등록됨",
  processing: "적재 중",
  completed: "적재 완료",
  failed: "적재 실패",
};

export default function GraphSources({ open, projectId, projectTitle }) {
  const { data, error, mutate } = useSWR(
    open ? storeKeys.graphSources(projectId) : null,
    () => api.listGraphSources(projectId),
    { refreshInterval: (current) => current?.sources?.some((s) => s.status === "processing") ? 2000 : 0 }
  );
  const [form, setForm] = useState({ name: "로컬 문서", path: "" });
  const [saving, setSaving] = useState(false);
  const [ingestingId, setIngestingId] = useState(null);
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (data?.shared_root) {
      setForm((current) => current.path ? current : { ...current, path: data.shared_root });
    }
  }, [data?.shared_root]);

  async function register(e) {
    e.preventDefault();
    setSaving(true);
    setMessage("");
    try {
      await api.registerGraphSource(projectId, form);
      setMessage("경로를 등록했습니다. ‘적재’ 버튼으로 문서를 저장하세요.");
      await mutate();
      swrMutate(storeKeys.projectGraph(projectId));
    } catch (err) {
      setMessage(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function ingest(source) {
    setIngestingId(source.id);
    setMessage(`${source.name} 문서를 읽고 있습니다…`);
    try {
      const result = await api.ingestGraphSource(projectId, source.id);
      setMessage(`적재 완료: 문서 ${result.document_count}개 · 본문 조각 ${result.chunk_count}개 · 문서 링크 ${result.link_count}개`);
    } catch (err) {
      setMessage(err.message);
    } finally {
      setIngestingId(null);
      mutate();
      swrMutate(storeKeys.projectGraph(projectId));
    }
  }

  async function assign(source) {
    setIngestingId(source.id);
    setMessage("");
    try {
      await api.assignGraphSource(projectId, source.id);
      setMessage("기존 소스를 이 프로젝트에 연결했습니다. 적재한 문서는 Stage의 그래프에서 확인하세요.");
      await mutate();
      swrMutate(storeKeys.projectGraph(projectId));
    } catch (err) {
      setMessage(err.message);
    } finally {
      setIngestingId(null);
    }
  }

  if (!projectId) return <section><h3>Graph RAG 데이터 소스</h3><p className="muted small">사이드바에서 프로젝트를 선택한 뒤 경로를 등록하세요.</p></section>;

  return <section>
    <h3>Graph RAG 데이터 소스</h3>
    <p className="small">프로젝트: <strong>{projectTitle || projectId}</strong></p>
    <p className="muted small">폴더 또는 파일 경로를 등록하고 ‘적재’를 누르면 문서 본문과 문서 간 링크를 Neo4j에 저장합니다. 이 프로젝트의 데이터로 저장하며 원본 파일은 읽기만 합니다.</p>
    <p className="muted small">지원: Markdown(.md), 텍스트(.txt). 질문에서 검색하는 연결은 준비 중입니다.</p>
    {data?.shared_root ? <p className="muted small">공유 폴더: <span className="graph-source-path">{data.shared_root}</span></p> : null}
    <form className="admin-form" onSubmit={register}>
      <label>이름<input required maxLength={200} value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} /></label>
      <label>폴더 또는 파일 경로<input required maxLength={2000} value={form.path} onChange={(e) => setForm((f) => ({ ...f, path: e.target.value }))} placeholder="공유 폴더 안의 경로" /></label>
      <button type="submit" className="primary" disabled={saving || !data || !!ingestingId}>{saving ? "등록 중…" : "경로 등록"}</button>
    </form>
    {error ? <p className="admin-status" role="alert">{error.message}</p> : null}
    <ul className="graph-source-list">
      {(data?.sources || []).map((source) => <li key={source.id}>
        <div className="graph-source-heading"><strong>{source.name}</strong><span className="muted small">{statusLabels[source.status]}</span></div>
        <p className="graph-source-path small">{source.path}</p>
        <p className="muted small">문서 {source.document_count}개 · 본문 조각 {source.chunk_count}개 · 링크 {source.link_count}개</p>
        {source.skipped_count ? <p className="muted small">지원하지 않는 파일·빈 문서 {source.skipped_count}개 제외</p> : null}
        {source.unresolved_link_count ? <p className="muted small">대상을 찾지 못한 문서 링크 {source.unresolved_link_count}개</p> : null}
        {source.last_ingested_at ? <p className="muted small">마지막 적재: {new Date(source.last_ingested_at).toLocaleString("ko-KR")}</p> : null}
        {source.error ? <p className="admin-status" role="alert">{source.error}</p> : null}
        <button type="button" className="ghost" disabled={!!ingestingId} onClick={() => ingest(source)}>{ingestingId === source.id ? "적재 중…" : "적재"}</button>
      </li>)}
    </ul>
    {data && !data.sources.length ? <p className="muted small">등록된 경로가 없습니다.</p> : null}
    {data?.unassigned_sources?.length ? <div className="graph-unassigned">
      <h4>프로젝트에 연결되지 않은 기존 소스</h4>
      <p className="muted small">기존 경로와 적재 데이터는 보존되어 있습니다. 사용할 프로젝트를 선택해 연결하세요.</p>
      <ul className="graph-source-list">{data.unassigned_sources.map((source) => <li key={source.id}>
        <strong>{source.name}</strong><p className="graph-source-path small">{source.path}</p>
        <button type="button" className="ghost" disabled={!!ingestingId || saving} onClick={() => assign(source)}>{ingestingId === source.id ? "연결 중…" : "이 프로젝트에 연결"}</button>
      </li>)}</ul>
    </div> : null}
    {message ? <p className="admin-status" role="status">{message}</p> : null}
  </section>;
}
