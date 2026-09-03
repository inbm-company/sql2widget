import { useEffect, useState } from "react";
import { Routes, Route, Link } from "react-router-dom";
import { mutate as swrMutate } from "swr";
import {
  api,
  clearTokens,
  getAccessToken,
  setTokens,
} from "./api";
import { SOC_SAMPLE_QUESTIONS, GLOBAL_SAMPLE_QUESTIONS } from "./constants.js";
import AdminPanel from "./AdminPanel.jsx";
import StageCanvas, { addWidgetToStage } from "./StageCanvas.jsx";
import ViewerStagePage from "./ViewerStagePage.jsx";
import { canShowSql, resolveWidgetSql } from "./sqlHelpers.js";
import { storeKeys, useSWR } from "./store";
import WidgetRenderer from "./widgets/WidgetRenderer.jsx";

function LoginForm({ onSuccess }) {
  const [email, setEmail] = useState("admin@example.com");
  const [password, setPassword] = useState("demo-password");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const res = await api.login(email, password);
      setTokens(res);
      onSuccess(res.user);
    } catch (err) {
      setError(err.message || "로그인 실패");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-screen">
      <div className="login-stage-pane">
        <header className="stage-header">
          <h2>Stage</h2>
          <span className="save-status">핀 1</span>
        </header>
        <div className="stage-canvas login-stage-canvas">
          <form className="stage-widget login-pin" onSubmit={submit}>
            <div className="widget-chrome">
              <span className="widget-drag-handle" aria-hidden="true">
                ⋮⋮
              </span>
              <h1 className="widget-title">agent4any</h1>
            </div>
            <div className="widget-body login-pin-body">
              <p className="lede">질문을 위젯으로 받고, Stage에 꽂습니다.</p>
              <label>
                Email
                <input
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="username"
                />
              </label>
              <label>
                Password
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                />
              </label>
              {error ? <p className="error">{error}</p> : null}
              <button type="submit" className="primary" disabled={busy}>
                {busy ? "로그인 중…" : "로그인"}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}

function ArtifactPreviewCard({ widget, artifact, conversationId, onAdded, readOnly = false }) {
  const [showSql, setShowSql] = useState(false);
  const sql = resolveWidgetSql(widget);
  const sqlAvailable = canShowSql(widget) && Boolean(sql);

  function onDragStart(e) {
    e.dataTransfer.setData(
      "application/x-agent4any-widget",
      JSON.stringify({
        widget_id: widget.widget_id,
        artifact_id: artifact.artifact_id,
        component: widget.component,
        title: widget.title,
        props: widget.props,
        sql,
      })
    );
    e.dataTransfer.effectAllowed = "copy";
  }

  async function addDirect() {
    await addWidgetToStage(conversationId, {
      widget_id: widget.widget_id,
      artifact_id: artifact.artifact_id,
      component: widget.component,
      title: widget.title,
      props: widget.props,
      sql,
    });
    onAdded?.();
  }

  return (
    <div
      className="artifact-preview"
      draggable={!readOnly && !showSql}
      onDragStart={readOnly ? undefined : onDragStart}
    >
      <div className="artifact-preview-head">
        {!readOnly ? (
          <span className="drag-hint" title="스테이지로 드래그">
            ⠿
          </span>
        ) : null}
        <span className="artifact-title">{widget.title || widget.component}</span>
        <div className="artifact-actions">
          {sqlAvailable ? (
            <button
              type="button"
              className="text-btn"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                setShowSql((v) => !v);
              }}
              onMouseDown={(e) => e.stopPropagation()}
              onDragStart={(e) => e.preventDefault()}
            >
              {showSql ? "Widget" : "SQL"}
            </button>
          ) : null}
          {!readOnly ? (
            <button
              type="button"
              className="text-btn"
              onClick={(e) => {
                e.stopPropagation();
                addDirect();
              }}
              onMouseDown={(e) => e.stopPropagation()}
            >
              Add to stage
            </button>
          ) : null}
        </div>
      </div>
      {showSql && sqlAvailable ? (
        <pre className="sql-panel">{sql}</pre>
      ) : (
        <WidgetRenderer component={widget.component} props={widget.props} compact />
      )}
    </div>
  );
}

function AssistantAnswer({ content, artifact, conversationId, onAdded, readOnly = false }) {
  const [view, setView] = useState("widget");
  const hasArtifact = Boolean(artifact?.widgets?.length || artifact?.artifact_id);

  return (
    <div className="assistant-block">
      {content ? <div className="msg-content">{content}</div> : null}

      {hasArtifact ? (
        <div className="artifact-section">
          <div className="artifact-section-head">
            <span className="artifact-type">{artifact.type || "artifact"}</span>
            <div className="segmented" role="group" aria-label="View mode">
              <button
                type="button"
                className={view === "widget" ? "active" : ""}
                onClick={() => setView("widget")}
              >
                Widget
              </button>
              <button
                type="button"
                className={view === "json" ? "active" : ""}
                onClick={() => setView("json")}
              >
                JSON
              </button>
            </div>
          </div>

          {view === "json" ? (
            <pre className="artifact-json">{JSON.stringify(artifact, null, 2)}</pre>
          ) : (
            <div className="artifact-widgets">
              {(artifact.widgets || []).map((w) => (
                <ArtifactPreviewCard
                  key={w.widget_id}
                  widget={w}
                  artifact={artifact}
                  conversationId={conversationId}
                  onAdded={onAdded}
                  readOnly={readOnly}
                />
              ))}
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}

function ConversationItem({
  conv,
  active,
  onSelect,
  onRenamed,
  onDeleted,
  readOnly = false,
}) {
  const [renaming, setRenaming] = useState(false);
  const [draft, setDraft] = useState(conv.title);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!renaming) setDraft(conv.title);
  }, [conv.title, renaming]);

  async function saveRename() {
    const title = draft.trim();
    if (!title || title === conv.title) {
      setRenaming(false);
      setDraft(conv.title);
      return;
    }
    setBusy(true);
    try {
      await api.updateConversation(conv.id, title);
      onRenamed?.();
      setRenaming(false);
    } catch {
      setDraft(conv.title);
      setRenaming(false);
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!window.confirm("정말로 삭제하시겠습니까?")) return;
    setBusy(true);
    try {
      await api.deleteConversation(conv.id);
      onDeleted?.(conv.id);
    } finally {
      setBusy(false);
    }
  }

  if (renaming) {
    return (
      <li className="conv-item conv-item--editing">
        <input
          className="conv-rename-input"
          value={draft}
          autoFocus
          disabled={busy}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              saveRename();
            }
            if (e.key === "Escape") {
              setRenaming(false);
              setDraft(conv.title);
            }
          }}
          onBlur={() => saveRename()}
        />
      </li>
    );
  }

  return (
    <li className={`conv-item ${active ? "active" : ""}`}>
      <button
        type="button"
        className="conv-item-btn"
        onClick={() => onSelect(conv.id)}
        disabled={busy}
      >
        {conv.title}
      </button>
      <div className="conv-item-actions">
        {!readOnly ? (
          <>
            <button
              type="button"
              className="conv-action-btn"
              title="이름 변경"
              disabled={busy}
              onClick={(e) => {
                e.stopPropagation();
                setRenaming(true);
              }}
            >
              ✎
            </button>
            <button
              type="button"
              className="conv-action-btn conv-action-btn--danger"
              title="삭제"
              disabled={busy}
              onClick={(e) => {
                e.stopPropagation();
                remove();
              }}
            >
              ×
            </button>
          </>
        ) : null}
      </div>
    </li>
  );
}

function Workspace({ user, onLogout }) {
  const isViewer = user.role === "viewer";
  const canEdit = !isViewer;
  const [activeId, setActiveId] = useState(null);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [chatError, setChatError] = useState("");
  const [adminOpen, setAdminOpen] = useState(false);
  const [stageOpen, setStageOpen] = useState(true);
  const [connectionId, setConnectionId] = useState("");

  const { data: conversations, mutate: mutateConvs } = useSWR(
    storeKeys.conversations,
    () => api.listConversations()
  );

  const { data: conversation, mutate: mutateConv } = useSWR(
    storeKeys.conversation(activeId),
    () => api.getConversation(activeId)
  );

  const { data: connections } = useSWR(storeKeys.connections, () =>
    api.listConnections()
  );

  useEffect(() => {
    if (!connectionId && connections?.length) {
      setConnectionId(connections[0].id);
    }
  }, [connections, connectionId]);

  async function newChat() {
    const conv = await api.createConversation("New Chat");
    await mutateConvs();
    setActiveId(conv.id);
  }

  async function sendMessage(text) {
    const message = text.trim();
    if (!message || !activeId || sending) return;
    setSending(true);
    setChatError("");
    if (text === input) setInput("");
    try {
      await api.chat(activeId, message, connectionId || null);
      await mutateConv();
      await mutateConvs();
      await swrMutate(storeKeys.stage(activeId));
    } catch (err) {
      setChatError(err?.message || "응답 생성에 실패했습니다. 다시 시도해 주세요.");
      if (text === input || !input) setInput(message);
    } finally {
      setSending(false);
    }
  }

  async function send() {
    await sendMessage(input);
  }

  async function handleConversationDeleted(deletedId) {
    const remaining = (conversations || []).filter((c) => c.id !== deletedId);
    if (activeId === deletedId) {
      setActiveId(remaining[0]?.id ?? null);
      await swrMutate(storeKeys.conversation(deletedId), undefined, { revalidate: false });
      await swrMutate(storeKeys.stage(deletedId), undefined, { revalidate: false });
    }
    await mutateConvs();
  }

  const activeTitle =
    conversations?.find((c) => c.id === activeId)?.title || "Chat";

  const isGlobalDb = connectionId === "dbconn_global";
  const sampleQuestions = isGlobalDb ? GLOBAL_SAMPLE_QUESTIONS : SOC_SAMPLE_QUESTIONS;

  return (
    <div className={`workspace ${stageOpen ? "" : "stage-collapsed"}`}>
      <aside className="sidebar">
        <div className="sidebar-top">
          <div className="brand">agent4any</div>
          <button type="button" className="sidebar-new" onClick={newChat} title="New chat" disabled={isViewer}>
            <span className="sidebar-new-icon">+</span>
            New chat
          </button>
        </div>

        <ul className="conv-list" title="대화에 마우스를 올리면 이름 변경·삭제">
          {(conversations || []).map((c) => (
            <ConversationItem
              key={c.id}
              conv={c}
              active={c.id === activeId}
              onSelect={setActiveId}
              onRenamed={mutateConvs}
              onDeleted={handleConversationDeleted}
              readOnly={isViewer}
            />
          ))}
        </ul>

        <div className="sidebar-footer">
          <label className="conn-select">
            <span>Database</span>
            <select
              value={connectionId}
              onChange={(e) => setConnectionId(e.target.value)}
            >
              {(connections || []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <div className="sidebar-links">
            {user.role === "admin" ? (
              <button type="button" className="link-btn" onClick={() => setAdminOpen(true)}>
                Admin
              </button>
            ) : null}
            {activeId ? (
              <Link to={`/c/${activeId}/view`} className="link-btn">
                Open viewer
              </Link>
            ) : null}
            {canEdit ? (
              <button type="button" className="link-btn" onClick={() => setStageOpen((v) => !v)}>
                {stageOpen ? "Hide stage" : "Show stage"}
              </button>
            ) : null}
            <button type="button" className="link-btn" onClick={onLogout}>
              Sign out
            </button>
          </div>
          <div className="user-email">{user.email}</div>
        </div>
      </aside>

      <main className="chat-pane">
        {!activeId ? (
          <div className="chat-empty">
            <p className="chat-empty-title">What would you like to know?</p>
            <p className="muted">Ask about SOC security data, then drag widgets to the stage.</p>
            <button type="button" className="primary" onClick={newChat}>
              New chat
            </button>
          </div>
        ) : (
          <>
            <header className="chat-header">
              <h1 className="chat-title">{activeTitle}</h1>
              {activeId ? (
                <Link to={`/c/${activeId}/view`} className="chat-view-link">
                  Viewer ↗
                </Link>
              ) : null}
            </header>

            <div className="messages">
              {(conversation?.messages || []).length === 0 ? (
                <div className="prompt-suggestions">
                  <p className="prompt-label">Suggested</p>
                  {sampleQuestions.map((q) => (
                    <button
                      key={q}
                      type="button"
                      className="prompt-row"
                      onClick={() => sendMessage(q)}
                      disabled={sending || isViewer}
                    >
                      {q}
                    </button>
                  ))}
                </div>
              ) : null}

              {(conversation?.messages || []).map((m) => (
                <div key={m.id} className={`msg ${m.role}`}>
                  {m.role === "user" ? (
                    <div className="msg-content user-bubble">{m.content}</div>
                  ) : (
                    <AssistantAnswer
                      content={m.content}
                      artifact={m.artifact}
                      conversationId={activeId}
                      onAdded={() => swrMutate(storeKeys.stage(activeId))}
                      readOnly={isViewer}
                    />
                  )}
                </div>
              ))}
            </div>

            {canEdit ? (
              <div className="composer-wrap">
                {chatError ? <p className="error chat-send-error">{chatError}</p> : null}
                <div className="composer-box">
                  <textarea
                    rows={1}
                    value={input}
                    placeholder="Ask a question…"
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        send();
                      }
                    }}
                  />
                  <div className="composer-bar">
                    <span className="composer-hint">Enter to send · Shift+Enter for newline</span>
                    <button
                      type="button"
                      className="composer-send"
                      disabled={sending || !input.trim()}
                      onClick={send}
                      aria-label="Send"
                    >
                      ↑
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <div className="composer-wrap viewer-readonly-hint">
                <p className="muted">Viewer 모드 — 채팅 입력은 비활성화됩니다.</p>
              </div>
            )}
          </>
        )}
      </main>

      <section className={`stage-pane ${stageOpen && canEdit ? "" : "is-hidden"}`}>
        <StageCanvas conversationId={activeId} readOnly={isViewer} />
      </section>

      <AdminPanel open={adminOpen} onClose={() => setAdminOpen(false)} />
    </div>
  );
}

export default function App() {
  const [user, setUser] = useState(null);
  const [booting, setBooting] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function boot() {
      if (!getAccessToken()) {
        setBooting(false);
        return;
      }
      try {
        const me = await api.me();
        if (!cancelled) setUser(me);
      } catch {
        clearTokens();
      } finally {
        if (!cancelled) setBooting(false);
      }
    }
    boot();
    return () => {
      cancelled = true;
    };
  }, []);

  if (booting) {
    return <div className="boot">Loading…</div>;
  }

  if (!user) {
    return <LoginForm onSuccess={setUser} />;
  }

  return (
    <Routes>
      <Route
        path="/c/:conversationId/view"
        element={
          <ViewerStagePage
            user={user}
            onLogout={() => {
              clearTokens();
              setUser(null);
            }}
          />
        }
      />
      <Route
        path="*"
        element={
          <Workspace
            user={user}
            onLogout={() => {
              clearTokens();
              setUser(null);
            }}
          />
        }
      />
    </Routes>
  );
}
