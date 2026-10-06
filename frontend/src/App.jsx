import { useEffect, useRef, useState } from "react";
import { Routes, Route, Link } from "react-router-dom";
import { mutate as swrMutate } from "swr";
import {
  api,
  clearTokens,
  getAccessToken,
  setTokens,
} from "./api";
import {
  SOC_SAMPLE_QUESTIONS,
  GLOBAL_SAMPLE_QUESTIONS,
  NORTHWIND_SAMPLE_QUESTIONS,
} from "./constants.js";
import AdminPanel from "./AdminPanel.jsx";
import StageCanvas, { addWidgetToStage } from "./StageCanvas.jsx";
import ViewerStagePage from "./ViewerStagePage.jsx";
import { canShowSql, resolveWidgetSql } from "./sqlHelpers.js";
import { storeKeys, useSWR } from "./store";
import WidgetRenderer from "./widgets/WidgetRenderer.jsx";
import ChatTrace from "./ChatTrace.jsx";

function LoginForm({ onSuccess }) {
  // 개발 서버(vite dev)에서만 데모 계정을 미리 채운다. 운영 빌드에서는 빈 값이며 문자열도 번들에서 제거된다.
  const [email, setEmail] = useState(import.meta.env.DEV ? (import.meta.env.VITE_DEV_ADMIN_EMAIL || "admin.local@example.com") : "");
  const [password, setPassword] = useState(import.meta.env.DEV ? "demo-password" : "");
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
              <h1 className="widget-title">sql2widget</h1>
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

function ArtifactPreviewCard({ widget, artifact, projectId, onAdded, readOnly = false }) {
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
    await addWidgetToStage(projectId, {
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

function AssistantAnswer({ content, artifact, meta, projectId, onAdded, onChoose, readOnly = false }) {
  const [view, setView] = useState("widget");
  const hasArtifact = Boolean(artifact?.widgets?.length || artifact?.artifact_id);

  return (
    <div className="assistant-block">
      {content ? <div className="msg-content">{content}</div> : null}
      <ChatTrace meta={meta} />


      {artifact?.choices?.length ? (
        <div className="prompt-suggestions">
          {artifact.choices.map((choice) => (
            <button
              key={`${choice.route}:${choice.action?.type || ""}:${choice.label}`}
              type="button"
              className="prompt-row"
              onClick={() => onChoose(choice)}
              disabled={readOnly}
            >
              {choice.label}
            </button>
          ))}
        </div>
      ) : null}

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
                  projectId={projectId}
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
  const [deleteError, setDeleteError] = useState("");

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
    setBusy(true);
    setDeleteError("");
    try {
      await api.deleteConversation(conv.id);
      onDeleted?.(conv.id);
    } catch (err) {
      setDeleteError(err?.message || "삭제하지 못했습니다.");
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
      {deleteError ? <span className="conv-delete-error">{deleteError}</span> : null}
    </li>
  );
}

function ProjectHeader({ project, active, onToggle, onRenamed, onNewChat, onDeleted, deletingDisabled = false, readOnly = false }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(project.title);
  const [busy, setBusy] = useState(false);
  const [deleteError, setDeleteError] = useState("");

  useEffect(() => {
    if (!editing) setDraft(project.title);
  }, [project.title, editing]);

  async function saveRename() {
    const title = draft.trim();
    if (!title || title === project.title) {
      setEditing(false);
      setDraft(project.title);
      return;
    }
    setBusy(true);
    try {
      await api.updateProject(project.id, title);
      await onRenamed?.();
      setEditing(false);
    } catch {
      setDraft(project.title);
      setEditing(false);
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (busy || readOnly || deletingDisabled) return;
    if (!window.confirm(`“${project.title}” 프로젝트를 삭제할까요?\n\n모든 대화·메시지와 Stage 위젯이 함께 삭제되며 복구할 수 없습니다.`)) return;
    setBusy(true);
    setDeleteError("");
    try {
      await api.deleteProject(project.id);
      await onDeleted?.(project.id);
    } catch (err) {
      setDeleteError(err?.message || "프로젝트를 삭제하지 못했습니다. 다시 시도해 주세요.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={`project-header ${active ? "active" : ""} ${editing ? "project-header--editing" : ""}`}>
      {editing ? (
        <input
          className="project-rename-input"
          value={draft}
          autoFocus
          disabled={busy}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              event.currentTarget.blur();
            }
            if (event.key === "Escape") {
              setDraft(project.title);
              setEditing(false);
            }
          }}
          onBlur={saveRename}
        />
      ) : (
        <button
          type="button"
          className="project-item"
          disabled={busy}
          title={readOnly ? project.title : "더블 클릭하여 이름 변경"}
          onClick={(event) => {
            if (event.detail === 1) onToggle();
          }}
          onDoubleClick={() => {
            if (readOnly) return;
            onToggle(true);
            setEditing(true);
          }}
        >
          <span>{project.title}</span>
        </button>
      )}
      {!editing ? (
        <div className="project-actions">
          {active ? (
            <button
              type="button"
              className="project-new-chat project-new-chat--header"
              onClick={(event) => {
                event.stopPropagation();
                onNewChat(project.id);
              }}
              disabled={readOnly || busy}
              aria-label="New chat"
              title="New chat"
            >
              +
            </button>
          ) : null}
          {!readOnly ? (
            <button
              type="button"
              className="project-delete conv-action-btn conv-action-btn--danger"
              aria-label={`프로젝트 삭제: ${project.title}`}
              title={deletingDisabled ? "응답이 완료된 후 삭제할 수 있습니다." : "프로젝트 삭제"}
              disabled={busy || deletingDisabled}
              onClick={remove}
            >
              ×
            </button>
          ) : null}
        </div>
      ) : null}
      {deleteError ? <p className="project-delete-error" role="alert">{deleteError}</p> : null}
    </div>
  );
}

function Workspace({ user, onLogout }) {
  const isViewer = user.role === "viewer";
  const canEdit = !isViewer;
  const [activeProjectId, setActiveProjectId] = useState(null);
  const [activeId, setActiveId] = useState(null);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [pendingMessage, setPendingMessage] = useState("");
  const [chatError, setChatError] = useState("");
  const [newChatError, setNewChatError] = useState("");
  const [adminOpen, setAdminOpen] = useState(false);
  const [settingsMode, setSettingsMode] = useState("admin");
  const [stageOpen, setStageOpen] = useState(true);
  const [connectionId, setConnectionId] = useState("");
  const messagesRef = useRef(null);
  const workspaceRef = useRef(null);
  const [chatShare, setChatShare] = useState(1 / 2.1);
  const resizeStart = useRef(null);

  function resizeChat(clientX) {
    const workspace = workspaceRef.current;
    if (!workspace) return;
    const sidebar = workspace.querySelector(".sidebar").getBoundingClientRect();
    const available = workspace.getBoundingClientRect().right - sidebar.right - 8;
    if (available < 660) return;
    setChatShare(Math.max(320, Math.min(available - 340, clientX - sidebar.right)) / available);
  }

  const { data: projects, mutate: mutateProjects } = useSWR(
    storeKeys.projects,
    () => api.listProjects()
  );

  const { data: conversations, mutate: mutateConvs } = useSWR(
    storeKeys.conversations(activeProjectId),
    () => api.listConversations(activeProjectId)
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

  useEffect(() => {
    if (sending) {
      messagesRef.current?.scrollTo({ top: messagesRef.current.scrollHeight, behavior: "smooth" });
    }
  }, [sending]);

  async function newProject() {
    const project = await api.createProject("새 프로젝트");
    await mutateProjects();
    setActiveProjectId(project.id);
    setActiveId(null);
  }

  async function newChat(projectId = activeProjectId) {
    if (!projectId) return;
    setNewChatError("");
    try {
      const conv = await api.createConversation(projectId, "New Chat");
      if (projectId === activeProjectId) await mutateConvs();
      await mutateProjects();
      setActiveProjectId(projectId);
      setActiveId(conv.id);
    } catch (err) {
      setNewChatError(err?.message || "새 챗을 만들지 못했습니다. 다시 시도해 주세요.");
    }
  }

  async function sendMessage(text, route = null) {
    const message = text.trim();
    if (!message || !activeId || sending) return;
    setSending(true);
    setPendingMessage(message);
    setChatError("");
    if (text === input) setInput("");
    try {
      await api.chat(activeId, message, connectionId || null, route);
      await mutateConv();
      await mutateConvs();
      await swrMutate(storeKeys.stage(activeProjectId));
    } catch (err) {
      setChatError(err?.message || "응답 생성에 실패했습니다. 다시 시도해 주세요.");
      if (text === input || !input) setInput(message);
    } finally {
      setSending(false);
      setPendingMessage("");
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
    }
    await mutateConvs();
    await mutateProjects();
  }

  async function handleProjectDeleted(deletedId) {
    const deletedConversations = deletedId === activeProjectId ? conversations || [] : [];
    const deletedConversationKeys = new Set(deletedConversations.map((c) => storeKeys.conversation(c.id)));
    const deletedKeys = new Set([storeKeys.conversations(deletedId), storeKeys.stage(deletedId)]);
    setActiveProjectId((current) => current === deletedId ? null : current);
    setActiveId((current) => (deletedId === activeProjectId && current === activeId) || deletedConversationKeys.has(storeKeys.conversation(current)) ? null : current);
    if (deletedId === activeProjectId) {
      setInput("");
      setChatError("");
      setNewChatError("");
    }
    await swrMutate(
      (key) => deletedKeys.has(key) || deletedConversationKeys.has(key) ||
        (typeof key === "string" && key.startsWith(`api:/projects/${deletedId}/`)),
      undefined,
      { revalidate: false }
    );
    await mutateProjects((current) => (current || []).filter((p) => p.id !== deletedId), { revalidate: false });
  }

  const activeTitle =
    conversations?.find((c) => c.id === activeId)?.title || "Chat";
  const activeProject = projects?.find((p) => p.id === activeProjectId);

  const sampleQuestions =
    connectionId === "dbconn_global"
      ? GLOBAL_SAMPLE_QUESTIONS
      : connectionId === "dbconn_northwind"
        ? NORTHWIND_SAMPLE_QUESTIONS
        : SOC_SAMPLE_QUESTIONS;

  return (
    <div ref={workspaceRef} style={{ "--chat-share": `${chatShare}fr`, "--stage-share": `${1 - chatShare}fr` }} className={`workspace ${stageOpen && canEdit ? "" : "stage-collapsed"}`}>
      <aside className="sidebar">
        <div className="sidebar-top">
          <div className="brand">sql2widget</div>
          <button type="button" className="sidebar-new" onClick={newProject} title="New project" disabled={isViewer}>
            <span className="sidebar-new-icon">+</span>
            New project
          </button>
        </div>

        <div className="project-list">
          {(projects || []).map((project) => (
            <div key={project.id} className="project-group">
              <ProjectHeader
                project={project}
                active={project.id === activeProjectId}
                onToggle={(open) => {
                  setActiveProjectId((current) => open ? project.id : current === project.id ? null : project.id);
                  setActiveId(null);
                }}
                onRenamed={mutateProjects}
                onNewChat={newChat}
                onDeleted={handleProjectDeleted}
                deletingDisabled={sending && project.id === activeProjectId}
                readOnly={isViewer}
              />
              {project.id === activeProjectId ? (
                <div className="project-tree">
                  <ul className="conv-list project-conversations" title="대화에 마우스를 올리면 이름 변경·삭제">
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
                </div>
              ) : null}
            </div>
          ))}
        </div>

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
              <>
              <button type="button" className="link-btn" onClick={() => { setSettingsMode("admin"); setAdminOpen(true); }}>
                Admin
              </button>
              <button type="button" className="link-btn" onClick={() => { setSettingsMode("ai"); setAdminOpen(true); }}>
                AI 설정
              </button>
              <button type="button" className="link-btn" onClick={() => { setSettingsMode("db"); setAdminOpen(true); }}>
                DB 관리
              </button>
              </>
            ) : null}
            {activeProjectId ? (
              <Link to={`/p/${activeProjectId}/view`} className="link-btn">
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
        {newChatError ? <p className="error chat-send-error" role="alert">{newChatError}</p> : null}
        {!activeProjectId ? (
          <div className="chat-empty">
            <p className="chat-empty-title">프로젝트를 선택하세요.</p>
          </div>
        ) : !activeId ? (
          <div className="chat-empty">
            <p className="chat-empty-title">{activeProject?.title}</p>
            <p className="muted">이 프로젝트에 새 챗을 만들어 질문을 시작하세요.</p>
            <button type="button" className="primary" onClick={() => newChat()} disabled={isViewer}>
              New chat
            </button>
          </div>
        ) : (
          <>
            <header className="chat-header">
              <h1 className="chat-title">{activeTitle}</h1>
              {activeId ? (
                <Link to={`/p/${activeProjectId}/view`} className="chat-view-link">
                  Viewer ↗
                </Link>
              ) : null}
            </header>

            <div className="messages" ref={messagesRef}>
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
                      meta={m.meta}
                      projectId={activeProjectId}
                      onAdded={() => swrMutate(storeKeys.stage(activeProjectId))}
                      onChoose={(choice) => sendMessage(choice.message, choice.route)}
                      readOnly={isViewer || sending}
                    />
                  )}
                </div>
              ))}
              {sending ? (
                <>
                  <div className="msg user pending-user">
                    <div className="msg-content user-bubble">{pendingMessage}</div>
                  </div>
                  <div className="msg assistant assistant-pending" role="status" aria-live="polite">
                    <span className="loading-dots" aria-hidden="true">•••</span>
                    답변 생성 중…
                  </div>
                </>
              ) : null}
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
                    <span className="composer-hint">{sending ? "답변 생성 중…" : "Enter to send · Shift+Enter for newline"}</span>
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

      {stageOpen && canEdit ? (
        <div
          className="pane-resizer"
          role="separator"
          aria-label="채팅과 Stage 너비 조절"
          aria-orientation="vertical"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(chatShare * 100)}
          tabIndex={0}
          onPointerDown={(e) => {
            if (e.button !== 0) return;
            e.preventDefault();
            resizeStart.current = e.clientX;
            e.currentTarget.setPointerCapture(e.pointerId);
          }}
          onPointerMove={(e) => {
            if (resizeStart.current !== null) resizeChat(e.clientX);
          }}
          onPointerUp={(e) => {
            resizeStart.current = null;
            if (e.currentTarget.hasPointerCapture(e.pointerId)) e.currentTarget.releasePointerCapture(e.pointerId);
          }}
          onLostPointerCapture={() => { resizeStart.current = null; }}
          onPointerCancel={() => { resizeStart.current = null; }}
          onDoubleClick={() => setChatShare(1 / 2.1)}
          onKeyDown={(e) => {
            if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
            e.preventDefault();
            const chat = workspaceRef.current.querySelector(".chat-pane").getBoundingClientRect();
            resizeChat(chat.right + (e.key === "ArrowRight" ? 24 : -24));
          }}
        />
      ) : null}
      <section className={`stage-pane ${stageOpen && canEdit ? "" : "is-hidden"}`}>
        <StageCanvas projectId={activeProjectId} readOnly={isViewer} />
      </section>

      <AdminPanel projectId={activeProjectId} projectTitle={activeProject?.title} open={adminOpen} mode={settingsMode} onClose={() => setAdminOpen(false)} />
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
        path="/p/:projectId/view"
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
