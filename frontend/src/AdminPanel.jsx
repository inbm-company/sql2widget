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
            <p className="muted small">키는 이 브라우저에만 저장되고 채팅 요청에만 사용됩니다.</p>
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
