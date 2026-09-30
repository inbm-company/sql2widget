import { useEffect, useState } from "react";
import { api } from "./api";
import { storeKeys, useSWR } from "./store";

const statusLabels = {
  registered: "등록됨",
  processing: "적재 중",
  completed: "적재 완료",
  failed: "적재 실패",
};

export default function GraphSources({ open }) {
  const { data, error, mutate } = useSWR(
    open ? storeKeys.graphSources : null,
    () => api.listGraphSources(),
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
      await api.registerGraphSource(form);
      setMessage("경로를 등록했습니다. ‘적재’ 버튼으로 문서를 저장하세요.");
      await mutate();
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
      const result = await api.ingestGraphSource(source.id);
      setMessage(`적재 완료: 문서 ${result.document_count}개 · 본문 조각 ${result.chunk_count}개 · 문서 링크 ${result.link_count}개`);
    } catch (err) {
      setMessage(err.message);
    } finally {
      setIngestingId(null);
      mutate();
    }
  }

  return <section>
    <h3>Graph RAG 데이터 소스</h3>
    <p className="muted small">폴더 또는 파일 경로를 등록하고 ‘적재’를 누르면 문서 본문과 문서 간 링크를 Neo4j에 저장합니다. 원본 파일은 읽기만 합니다.</p>
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
    {message ? <p className="admin-status" role="status">{message}</p> : null}
  </section>;
}
