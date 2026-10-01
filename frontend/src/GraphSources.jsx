import { useState } from "react";
import { mutate as swrMutate } from "swr";
import { api } from "./api";
import { readUploadFiles } from "./graphUpload";
import { storeKeys, useSWR } from "./store";

const statusLabels = {
  registered: "등록됨",
  processing: "적재 중",
  completed: "적재 완료",
  failed: "적재 실패",
};

/** 폴더 선택과 파일 선택을 한 쌍의 버튼으로 보여주고, 선택 결과를 읽어 onPick으로 넘긴다. */
function FilePicker({ disabled, folderLabel = "폴더 선택", fileLabel = "파일 선택", onPick }) {
  async function change(event) {
    const input = event.target;
    const selected = Array.from(input.files || []);
    input.value = "";
    if (selected.length) await onPick(selected);
  }
  return <span className="graph-upload-actions">
    <label className="ghost file-pick" aria-disabled={disabled}>{folderLabel}
      <input type="file" webkitdirectory="" multiple disabled={disabled} onChange={change} />
    </label>
    <label className="ghost file-pick" aria-disabled={disabled}>{fileLabel}
      <input type="file" multiple accept=".md,.txt" disabled={disabled} onChange={change} />
    </label>
  </span>;
}

export default function GraphSources({ open, projectId, projectTitle }) {
  const { data, error, mutate } = useSWR(
    open ? storeKeys.graphSources(projectId) : null,
    () => api.listGraphSources(projectId),
    { refreshInterval: (current) => current?.sources?.some((s) => s.status === "processing") ? 2000 : 0 }
  );
  const [name, setName] = useState("로컬 문서");
  const [picked, setPicked] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const [message, setMessage] = useState("");
  const busy = !!busyId;

  async function pick(selected) {
    setMessage("문서를 읽고 있습니다…");
    try {
      const result = await readUploadFiles(selected);
      setPicked(result);
      setMessage(result.files.length
        ? ""
        : "올릴 수 있는 .md 또는 .txt 문서가 없습니다.");
    } catch (err) {
      setPicked(null);
      setMessage(err.message);
    }
  }

  async function upload(e) {
    e.preventDefault();
    if (!picked?.files.length) return;
    setBusyId("new");
    setMessage("업로드하고 있습니다…");
    try {
      await api.registerGraphSource(projectId, { name, files: picked.files });
      setPicked(null);
      setMessage("문서를 올렸습니다. ‘적재’ 버튼으로 Neo4j에 저장하세요.");
      await mutate();
    } catch (err) {
      setMessage(err.message);
    } finally {
      setBusyId(null);
    }
  }

  async function replaceFiles(source, selected) {
    setBusyId(source.id);
    setMessage(`${source.name} 문서를 읽고 있습니다…`);
    try {
      const { files, excluded } = await readUploadFiles(selected);
      if (!files.length) throw new Error("올릴 수 있는 .md 또는 .txt 문서가 없습니다.");
      await api.replaceGraphSourceFiles(projectId, source.id, files);
      setMessage(`문서 ${files.length}개로 교체했습니다${excluded ? ` (제외 ${excluded}개)` : ""}. ‘적재’를 눌러 그래프에 반영하세요.`);
      await mutate();
    } catch (err) {
      setMessage(err.message);
    } finally {
      setBusyId(null);
    }
  }

  async function ingest(source) {
    setBusyId(source.id);
    setMessage(`${source.name} 문서를 읽고 있습니다…`);
    try {
      const result = await api.ingestGraphSource(projectId, source.id);
      setMessage(`적재 완료: 문서 ${result.document_count}개 · 본문 조각 ${result.chunk_count}개 · 문서 링크 ${result.link_count}개`);
    } catch (err) {
      setMessage(err.message);
    } finally {
      setBusyId(null);
      mutate();
      swrMutate(storeKeys.projectGraph(projectId));
    }
  }

  if (!projectId) return <section><h3>Graph RAG 데이터 소스</h3><p className="muted small">사이드바에서 프로젝트를 선택한 뒤 문서를 올리세요.</p></section>;

  return <section>
    <h3>Graph RAG 데이터 소스</h3>
    <p className="small">프로젝트: <strong>{projectTitle || projectId}</strong></p>
    <p className="muted small">폴더나 파일을 올리고 ‘적재’를 누르면 문서 본문과 문서 간 링크를 Neo4j에 저장합니다. 올린 문서는 이 프로젝트의 데이터로 서버에 보관되며, 내용이 바뀌면 다시 올린 뒤 적재하세요.</p>
    <p className="muted small">지원: Markdown(.md), 텍스트(.txt). 숨김 폴더(.git, .obsidian 등)는 제외합니다. 질문에서 검색하는 연결은 준비 중입니다.</p>
    <form className="admin-form" onSubmit={upload}>
      <label>이름<input required maxLength={200} value={name} onChange={(e) => setName(e.target.value)} /></label>
      <div>
        <FilePicker disabled={busy} onPick={pick} />
        {picked?.files.length ? <p className="muted small">선택: 문서 {picked.files.length}개{picked.excluded ? ` · 제외 ${picked.excluded}개` : ""}</p> : null}
      </div>
      <button type="submit" className="primary" disabled={busy || !data || !picked?.files.length}>{busyId === "new" ? "업로드 중…" : "문서 올리기"}</button>
    </form>
    {error ? <p className="admin-status" role="alert">{error.message}</p> : null}
    <ul className="graph-source-list">
      {(data?.sources || []).map((source) => <li key={source.id}>
        <div className="graph-source-heading"><strong>{source.name}</strong><span className="muted small">{statusLabels[source.status]}</span></div>
        <p className="muted small">{source.file_count ? `올린 문서 ${source.file_count}개` : "올린 문서 없음 — 아래에서 문서를 다시 올리세요."}</p>
        <p className="muted small">적재 결과: 문서 {source.document_count}개 · 본문 조각 {source.chunk_count}개 · 링크 {source.link_count}개</p>
        {source.skipped_count ? <p className="muted small">빈 문서 {source.skipped_count}개 제외</p> : null}
        {source.unresolved_link_count ? <p className="muted small">대상을 찾지 못한 문서 링크 {source.unresolved_link_count}개</p> : null}
        {source.last_ingested_at ? <p className="muted small">마지막 적재: {new Date(source.last_ingested_at).toLocaleString("ko-KR")}</p> : null}
        {source.error ? <p className="admin-status" role="alert">{source.error}</p> : null}
        <span className="graph-upload-actions">
          <button type="button" className="ghost" disabled={busy || !source.file_count} onClick={() => ingest(source)}>{busyId === source.id ? "처리 중…" : "적재"}</button>
          <FilePicker disabled={busy} folderLabel="폴더 다시 올리기" fileLabel="파일 다시 올리기" onPick={(selected) => replaceFiles(source, selected)} />
        </span>
      </li>)}
    </ul>
    {data && !data.sources.length ? <p className="muted small">올린 문서가 없습니다.</p> : null}
    {message ? <p className="admin-status" role="status">{message}</p> : null}
  </section>;
}
