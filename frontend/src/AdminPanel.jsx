import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { api, getAiSettings, setAiSettings } from "./api";
import { storeKeys, useSWR } from "./store";

export default function AdminPanel({ open, onClose, mode = "admin", projectId, projectTitle }) {
  const showAi = mode !== "db";
  const showDb = mode !== "ai";
  const title = mode === "ai" ? "AI 설정" : mode === "db" ? "DB 관리" : "관리자";
  const { data: connections, mutate } = useSWR(
    open && showDb ? storeKeys.connections : null,
    () => api.listConnections()
  );
  const [selectedId, setSelectedId] = useState("");
  const { data: savedQuestions, mutate: mutateQuestions } = useSWR(
    open && showDb && selectedId ? storeKeys.questions(selectedId) : null,
    () => api.listQuestions(selectedId)
  );
  const [tables, setTables] = useState([]);
  const [perms, setPerms] = useState([]);
  const [selectedTables, setSelectedTables] = useState([]);
  const [status, setStatus] = useState("");
  const [seeding, setSeeding] = useState(false);
  const [seedResult, setSeedResult] = useState(null);
  const [aiSettings, setAiForm] = useState(() => getAiSettings(getAiSettings().provider || "gemini"));
  const [aiDrafts, setAiDrafts] = useState({});
  const [localModels, setLocalModels] = useState(null);
  const [localModelsError, setLocalModelsError] = useState("");
  const [loadingModels, setLoadingModels] = useState(false);

  async function loadLocalModels() {
    setLoadingModels(true);
    setLocalModelsError("");
    try {
      const res = await api.listLocalModels(aiSettings.baseUrl, aiSettings.apiKey);
      setLocalModels(res.models);
    } catch (err) {
      setLocalModels(null);
      setLocalModelsError(err.message);
    } finally {
      setLoadingModels(false);
    }
  }

  useEffect(() => {
    if (!open || !showAi || aiSettings.provider !== "local") return;
    loadLocalModels();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, showAi, aiSettings.provider]);

  function modelSelect(field, value, optional) {
    const names = localModels.includes(value) || !value ? localModels : [value, ...localModels];
    return (
      <select required={!optional} value={value} onChange={(e) => setAiForm((f) => ({ ...f, [field]: e.target.value }))}>
        <option value="">{optional ? "사용 안 함" : "모델 선택"}</option>
        {names.map((name) => <option key={name} value={name}>{name}</option>)}
      </select>
    );
  }

  function switchProvider(provider) {
    setAiDrafts((drafts) => ({ ...drafts, [aiSettings.provider]: aiSettings }));
    setAiForm(aiDrafts[provider] || getAiSettings(provider));
  }

  const [form, setForm] = useState({
    name: "",
    host: "db-customer",
    port: 5432,
    database_name: "agent4any_customer_demo",
    username: "agent4any",
    password: "agent4any",
  });

  useEffect(() => {
    if (open) setStatus("");
  }, [open, mode]);

  useEffect(() => {
    if (!selectedId && connections?.length) {
      setSelectedId(connections[0].id);
    }
  }, [connections, selectedId]);

  useEffect(() => {
    if (!open || !showDb || !selectedId) return undefined;
    let cancelled = false;
    (async () => {
      try {
        const [t, p] = await Promise.all([
          api.listTables(selectedId),
          api.getTablePermissions(selectedId),
        ]);
        if (cancelled) return;
        setTables(t);
        setPerms(p);
        setSelectedTables(
          p.filter((x) => x.role === "user").map((x) => x.table_name)
        );
      } catch (err) {
        if (!cancelled) setStatus(err.message);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open, showDb, selectedId]);

  async function createConn(e) {
    e.preventDefault();
    setStatus("저장 중…");
    try {
      await api.createConnection({ ...form, port: Number(form.port) });
      await mutate();
      setStatus("연결이 저장되었습니다.");
    } catch (err) {
      setStatus(err.message);
    }
  }

  async function testConn() {
    if (!selectedId) return;
    setStatus("테스트 중…");
    try {
      const res = await api.testConnection(selectedId);
      setStatus(res.ok ? "연결 성공" : "연결 실패");
    } catch (err) {
      setStatus(err.message);
    }
  }

  async function seedQuestions() {
    if (!selectedId || seeding) return;
    const connectionId = selectedId;
    let offset = seedResult?.connection_id === connectionId && seedResult.next_offset != null
      ? seedResult.next_offset : 0;
    let savedCount = offset ? seedResult.saved_count : 0;
    let skippedCount = offset ? seedResult.skipped_count : 0;
    let questions = offset ? seedResult.questions : [];
    let uncoveredTables = offset ? seedResult.uncovered_tables : [];
    setSeeding(true);
    if (!offset) setSeedResult(null);
    setStatus("DB 전체 스키마를 살펴보고 예상 질문을 생성·검증하고 있습니다…");
    try {
      while (true) {
        const result = await api.seedQuestions(connectionId, offset);
        savedCount += result.saved_count;
        skippedCount += result.skipped_count;
        questions = [...questions, ...result.questions];
        uncoveredTables = [...uncoveredTables, ...result.uncovered_tables];
        const processed = offset + result.processed_tables;
        setSeedResult({ connection_id: connectionId, questions, saved_count: savedCount,
          skipped_count: skippedCount, processed_tables: processed,
          total_tables: result.total_tables, next_offset: result.next_offset,
          uncovered_tables: uncoveredTables });
        setStatus(`${processed}/${result.total_tables}개 테이블 확인 · 예상 질문 ${savedCount}개 등록`
          + (uncoveredTables.length ? ` · 생성하지 못한 테이블 ${uncoveredTables.length}개` : ""));
        if (result.next_offset == null) break;
        if (result.next_offset <= offset) throw new Error("예상 질문 생성 진행 위치가 갱신되지 않았습니다.");
        offset = result.next_offset;
      }
    } catch (err) {
      setStatus(`예상 질문 생성이 중단되었습니다: ${err.message} 저장된 질문은 유지됩니다. 다시 누르면 이어서 진행합니다.`);
    } finally {
      setSeeding(false);
      mutateQuestions();
    }
  }

  async function savePerms() {
    if (!selectedId) return;
    setStatus("권한 저장 중…");
    try {
      await api.putTablePermissions({
        connection_id: selectedId,
        role: "user",
        tables: selectedTables.map((table_name) => ({
          schema_name: "public",
          table_name,
        })),
      });
      const p = await api.getTablePermissions(selectedId);
      setPerms(p);
      setStatus("권한을 저장했습니다.");
    } catch (err) {
      setStatus(err.message);
    }
  }

  function toggleTable(name) {
    setSelectedTables((prev) =>
      prev.includes(name) ? prev.filter((x) => x !== name) : [...prev, name]
    );
  }

  function saveAiSettings(e) {
    e.preventDefault();
    setAiSettings(aiSettings);
    setStatus("AI 연결 설정을 저장했습니다.");
  }

  if (!open) return null;

  return createPortal(
    <div
      className="admin-drawer"
      role="dialog"
      aria-modal="true"
      aria-label={title}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="admin-panel">
        <header>
          <h2>{title}</h2>
          <button type="button" className="ghost" onClick={onClose}>
            닫기
          </button>
        </header>

        {showAi ? <section>
          <h3>AI 연결</h3>
          <form className="admin-form" onSubmit={saveAiSettings}>
            <label>Provider
              <select value={aiSettings.provider} onChange={(e) => switchProvider(e.target.value)}>
                <option value="gemini">Gemini</option>
                <option value="openai">OpenAI 호환</option>
                <option value="local">로컬 모델 (OpenAI 호환)</option>
              </select>
            </label>
            {aiSettings.provider === "local" && localModels ? (
              <label>Model{modelSelect("model", aiSettings.model, false)}</label>
            ) : (
              <label>Model<input required value={aiSettings.model} onChange={(e) => setAiForm((f) => ({ ...f, model: e.target.value }))} placeholder={aiSettings.provider === "local" ? "로컬 서버에 설치된 모델 이름" : "모델 이름"} /></label>
            )}
            {aiSettings.provider !== "gemini" ? (
              <label>Base URL<input required type="url" value={aiSettings.baseUrl} onChange={(e) => setAiForm((f) => ({ ...f, baseUrl: e.target.value }))} /></label>
            ) : null}
            <label>API key{aiSettings.provider === "local" ? " (선택)" : ""}<input type="password" value={aiSettings.apiKey} onChange={(e) => setAiForm((f) => ({ ...f, apiKey: e.target.value }))} autoComplete="off" /></label>
            {aiSettings.provider === "local" ? <>
              {localModels ? (
                <label>Embedding model (선택){modelSelect("embeddingModel", aiSettings.embeddingModel, true)}</label>
              ) : (
                <label>Embedding model (선택)<input value={aiSettings.embeddingModel} onChange={(e) => setAiForm((f) => ({ ...f, embeddingModel: e.target.value }))} placeholder="예상 질문 생성·검색에 사용할 임베딩 모델" /></label>
              )}
              <button type="button" className="ghost" onClick={loadLocalModels} disabled={loadingModels}>{loadingModels ? "불러오는 중…" : "모델 목록 새로고침"}</button>
              {localModelsError ? <p className="muted small">모델 목록을 불러오지 못해 직접 입력합니다: {localModelsError}</p> : null}
              <p className="muted small">Base URL은 백엔드에서 접근할 주소입니다. Docker에서 호스트 서버에 연결할 때는 host.docker.internal을 사용하세요. 임베딩 모델이 없으면 채팅만 사용할 수 있습니다.</p>
            </> : null}
            <p className="muted small">설정은 Provider별로 이 브라우저에 저장됩니다. 저장한 Provider를 채팅과 예상 질문 생성·검색에 사용합니다.</p>
            <button type="submit" className="primary">AI 설정 저장</button>
          </form>
        </section> : null}

        {showDb ? <>
        <section>
          <h3>DB 연결</h3>
          <ul className="admin-list">
            {(connections || []).map((c) => (
              <li key={c.id}>
                <button
                  type="button"
                  className={c.id === selectedId ? "active" : ""}
                  disabled={seeding}
                  onClick={() => setSelectedId(c.id)}
                >
                  {c.name} ({c.host}/{c.database_name})
                </button>
              </li>
            ))}
          </ul>
          <div className="admin-actions">
            <button type="button" className="primary" onClick={testConn}>
              연결 테스트
            </button>
          </div>
        </section>

        <section>
          <h3>예상 질문 유사도 DB</h3>
          <p className="muted small">
            선택한 DB의 모든 테이블을 살펴보고 다양한 예상 질문과 SQL·위젯 정보를 준비합니다.
            채팅에서는 유사한 질문을 찾아 답변 생성에 참고합니다.
          </p>
          <button type="button" className="primary" disabled={!selectedId || seeding} onClick={seedQuestions}>
            {seeding ? "예상 질문 생성 중…" : seedResult?.connection_id === selectedId && seedResult.next_offset != null
              ? "이어서 생성" : "예상 질문 생성"}
          </button>
          {seeding || seedResult?.connection_id === selectedId ? (
            <p className="muted small" role="status">
              {seedResult?.connection_id === selectedId
                ? `${seedResult.processed_tables}/${seedResult.total_tables}개 테이블 확인 · 질문 ${seedResult.saved_count}개 등록`
                  + (seedResult.skipped_count ? ` · 검증 실패 ${seedResult.skipped_count}개` : "")
                : "DB 스키마를 확인하고 있습니다…"}
            </p>
          ) : null}
          <p className="muted small">AI가 DB 스키마를 보고 예상 질문과 SQL·위젯을 만듭니다. 실행 가능한 읽기 전용 SQL만 검증해 등록합니다.</p>
          {seedResult?.connection_id === selectedId && seedResult.uncovered_tables?.length ? (
            <p className="muted small">질문을 생성하지 못한 테이블: {seedResult.uncovered_tables.join(", ")}</p>
          ) : null}
          {savedQuestions ? (
            <p className="muted small">
              저장된 예상 질문 총 {savedQuestions.total}개
              {savedQuestions.total > savedQuestions.questions.length
                ? ` (최근 ${savedQuestions.questions.length}개 표시)` : ""}
            </p>
          ) : null}
          {savedQuestions?.questions?.length ? (
            <ul className="question-seed-list">
              {savedQuestions.questions.map((item) => (
                <li key={item.id}>
                  <details>
                    <summary>{item.question}</summary>
                    {item.plan.widgets.map((widget, index) => (
                      <div key={index}>
                        <p>{widget.title} · {widget.component}</p>
                        <pre className="sql-panel">{widget.sql}</pre>
                      </div>
                    ))}
                  </details>
                </li>
              ))}
            </ul>
          ) : null}
        </section>

        <section>
          <h3>새 연결 등록</h3>
          <form className="admin-form" onSubmit={createConn}>
            {["name", "host", "port", "database_name", "username", "password"].map(
              (key) => (
                <label key={key}>
                  {key}
                  <input
                    type={key === "password" ? "password" : "text"}
                    value={form[key]}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, [key]: e.target.value }))
                    }
                  />
                </label>
              )
            )}
            <button type="submit" className="primary">
              저장
            </button>
          </form>
        </section>

        <section>
          <h3>user 역할 테이블 권한</h3>
          <div className="perm-grid">
            {tables.map((t) => (
              <label key={`${t.schema_name}.${t.table_name}`} className="perm-item">
                <input
                  type="checkbox"
                  checked={selectedTables.includes(t.table_name)}
                  onChange={() => toggleTable(t.table_name)}
                />
                {t.schema_name}.{t.table_name}
              </label>
            ))}
          </div>
          <button type="button" className="primary" onClick={savePerms}>
            권한 저장
          </button>
          <p className="muted small">
            현재 user 권한:{" "}
            {perms
              .filter((p) => p.role === "user")
              .map((p) => p.table_name)
              .join(", ") || "(없음)"}
          </p>
        </section>

        </> : null}
        {status ? <p className="admin-status">{status}</p> : null}
      </div>
    </div>,
    document.body
  );
}
