import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { api, getAiSettings, setAiSettings } from "./api";
import { storeKeys, useSWR } from "./store";

export default function AdminPanel({ open, onClose }) {
  const { data: connections, mutate } = useSWR(
    open ? storeKeys.connections : null,
    () => api.listConnections()
  );
  const [selectedId, setSelectedId] = useState("");
  const [tables, setTables] = useState([]);
  const [perms, setPerms] = useState([]);
  const [selectedTables, setSelectedTables] = useState([]);
  const [status, setStatus] = useState("");
  const [seeding, setSeeding] = useState(false);
  const [commandRole, setCommandRole] = useState("user");
  const [seedResult, setSeedResult] = useState(null);
  const [aiSettings, setAiForm] = useState(() => ({ provider: "gemini", model: "gemini-3.6-flash", baseUrl: "https://generativelanguage.googleapis.com/v1beta/openai", apiKey: "", ...getAiSettings() }));
  const [form, setForm] = useState({
    name: "",
    host: "db-customer",
    port: 5432,
    database_name: "agent4any_customer_demo",
    username: "agent4any",
    password: "agent4any",
  });

  useEffect(() => {
    if (!selectedId && connections?.length) {
      setSelectedId(connections[0].id);
    }
  }, [connections, selectedId]);

  useEffect(() => {
    if (!open || !selectedId) return undefined;
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
  }, [open, selectedId]);

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

  async function seedCommands() {
    if (!selectedId || seeding) return;
    const connectionId = selectedId;
    setSeeding(true);
    setSeedResult(null);
    setStatus("DB 스키마를 읽고 초기 명령을 생성·검증하고 있습니다…");
    try {
      const result = await api.seedCommands(connectionId, commandRole);
      setSeedResult({ ...result, role: commandRole });
      setStatus(`초기 명령 ${result.saved_count}개를 유사도 DB에 저장했습니다.`);
    } catch (err) {
      setStatus(err.message);
    } finally {
      setSeeding(false);
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
    <div className="admin-drawer" role="dialog" aria-modal="true">
      <div className="admin-panel">
        <header>
          <h2>관리자</h2>
          <button type="button" className="ghost" onClick={onClose}>
            닫기
          </button>
        </header>

        <section>
          <h3>AI 연결</h3>
          <form className="admin-form" onSubmit={saveAiSettings}>
            <label>Provider<select value={aiSettings.provider} onChange={(e) => setAiForm((f) => ({ ...f, provider: e.target.value }))}><option value="gemini">Gemini</option><option value="openai">OpenAI 호환</option></select></label>
            <label>Model<input value={aiSettings.model} onChange={(e) => setAiForm((f) => ({ ...f, model: e.target.value }))} placeholder="gemini-3.6-flash" /></label>
            <label>API key<input type="password" value={aiSettings.apiKey} onChange={(e) => setAiForm((f) => ({ ...f, apiKey: e.target.value }))} placeholder="Gemini API key" autoComplete="off" /></label>
            <p className="muted small">키는 이 브라우저에만 저장되고 채팅과 명령 유사도 등록·검색에 사용됩니다.</p>
            <button type="submit" className="primary">AI 설정 저장</button>
          </form>
        </section>

        <section>
          <h3>DB 연결</h3>
          <ul className="admin-list">
            {(connections || []).map((c) => (
              <li key={c.id}>
                <button
                  type="button"
                  className={c.id === selectedId ? "active" : ""}
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
          <h3>명령 유사도 DB</h3>
          <p className="muted small">
            선택한 DB의 명령과 SQL·위젯 정보를 준비합니다. 채팅에서는 유사한 명령을 찾아 답변 생성에 참고합니다.
          </p>
          <label>테이블 권한 기준
            <select value={commandRole} disabled={seeding} onChange={(e) => setCommandRole(e.target.value)}>
              <option value="user">user</option>
              <option value="admin">admin</option>
              <option value="viewer">viewer</option>
            </select>
          </label>
          <button type="button" className="primary" disabled={!selectedId || seeding} onClick={seedCommands}>
            {seeding ? "초기 명령 준비 중…" : "초기 명령 3개 등록"}
          </button>
          <p className="muted small">AI 설정과 해당 역할의 테이블 권한을 먼저 저장하세요. SQL을 읽기 전용으로 검증한 뒤 등록합니다.</p>
          {seedResult?.connection_id === selectedId && seedResult.role === commandRole ? (
            <ul>
              {seedResult.commands.map((item) => (
                <li key={item.id}>
                  <details>
                    <summary>{item.command}</summary>
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

        {status ? <p className="admin-status">{status}</p> : null}
      </div>
    </div>,
    document.body
  );
}
