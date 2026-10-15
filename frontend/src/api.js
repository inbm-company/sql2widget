const API_BASE = import.meta.env.VITE_API_BASE ?? "";

const TOKEN_KEY = "sql2widget_access";
const REFRESH_KEY = "sql2widget_refresh";
export { getAiSettings, getJevApiKey, setAiSettings } from "./aiSettings";
import { getAiSettings, getJevApiKey } from "./aiSettings";

export function getAccessToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function getRefreshToken() {
  return localStorage.getItem(REFRESH_KEY);
}

export function setTokens({ access_token, refresh_token }) {
  if (access_token) localStorage.setItem(TOKEN_KEY, access_token);
  if (refresh_token) localStorage.setItem(REFRESH_KEY, refresh_token);
}

export function clearTokens() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

let refreshPromise = null;

async function refreshAccessToken() {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      const refresh_token = getRefreshToken();
      if (!refresh_token) throw new Error("No refresh token");
      const res = await fetch(`${API_BASE}/api/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token }),
      });
      if (!res.ok) {
        clearTokens();
        throw new Error("Refresh failed");
      }
      const data = await res.json();
      setTokens(data);
      return data.access_token;
    })().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

async function request(path, options = {}, { retry = true } = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };
  const token = getAccessToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (path === "/api/chat") {
    const jevApiKey = getJevApiKey();
    if (jevApiKey) headers["X-Jev-API-Key"] = jevApiKey;
  }
  if (path === "/api/chat" || /^\/api\/database-connections\/[^/]+\/questions(?:\/|$)/.test(path)) {
    const ai = getAiSettings();
    if (ai.apiKey) headers["X-LLM-API-Key"] = ai.apiKey;
    if (ai.provider) headers["X-LLM-Provider"] = ai.provider;
    if (ai.model) headers["X-LLM-Model"] = ai.model;
    if (ai.baseUrl) headers["X-LLM-Base-URL"] = ai.baseUrl;
    if (ai.provider) headers["X-LLM-Embedding-Model"] = ai.embeddingModel || "";
  }

  const controller = new AbortController();
  const timeoutMs = options.timeoutMs ?? 15000;
  const abortFromCaller = () => controller.abort(options.signal.reason);
  if (options.signal?.aborted) abortFromCaller();
  else options.signal?.addEventListener("abort", abortFromCaller, { once: true });
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let res;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers,
      signal: controller.signal,
    });

    if (res.status === 401 && retry && getRefreshToken() && !path.includes("/auth/")) {
      // Token refresh is shared; cancel only this caller's wait.
      await new Promise((resolve, reject) => {
        const abort = () => reject(controller.signal.reason);
        if (controller.signal.aborted) { abort(); return; }
        controller.signal.addEventListener("abort", abort, { once: true });
        const cleanup = () => controller.signal.removeEventListener("abort", abort);
        refreshAccessToken().then(
          (token) => { cleanup(); resolve(token); },
          (err) => { cleanup(); reject(err); },
        );
      });
      return await request(path, options, { retry: false });
    }

    if (!res.ok) {
      let detail = res.statusText;
      try {
        const body = await res.json();
        detail = body.detail || JSON.stringify(body);
      } catch (err) {
        if (controller.signal.aborted) throw err;
      }
      const err = new Error(detail);
      err.status = res.status;
      throw err;
    }

    if (res.status === 204) return null;
    return await res.json();
  } catch (err) {
    if (options.signal?.aborted) throw options.signal.reason;
    if (err?.name === "AbortError") {
      const timeoutErr = new Error(`Request timed out: ${path}`);
      timeoutErr.status = 0;
      throw timeoutErr;
    }
    throw err;
  } finally {
    clearTimeout(timer);
    options.signal?.removeEventListener("abort", abortFromCaller);
  }
}

export const api = {
  login: (email, password) =>
    request("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  me: () => request("/api/auth/me"),
  listProjects: () => request("/api/projects"),
  createProject: (title) =>
    request("/api/projects", {
      method: "POST",
      body: JSON.stringify({ title }),
    }),
  updateProject: (projectId, title) =>
    request(`/api/projects/${projectId}`, {
      method: "PATCH",
      body: JSON.stringify({ title }),
    }),
  deleteProject: (projectId) =>
    request(`/api/projects/${projectId}`, { method: "DELETE" }),
  listConversations: (projectId) =>
    request(`/api/conversations?project_id=${encodeURIComponent(projectId)}`),
  createConversation: (projectId, title) =>
    request("/api/conversations", {
      method: "POST",
      body: JSON.stringify({ project_id: projectId, title }),
    }),
  getConversation: (id) => request(`/api/conversations/${id}`),
  updateConversation: (id, title) =>
    request(`/api/conversations/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ title }),
    }),
  deleteConversation: (id) =>
    request(`/api/conversations/${id}`, {
      method: "DELETE",
    }),
  deleteMessage: (conversationId, messageId) =>
    request(`/api/conversations/${conversationId}/messages/${messageId}`, { method: "DELETE" }),
  chat: (conversationId, message, connectionId, route = null, signal = undefined, responseOptions = {}) =>
    request("/api/chat", {
      method: "POST",
      signal,
      // Allow the 180s agent loop plus embeddings and in-flight request overhead.
      timeoutMs: 360000,
      body: JSON.stringify({
        conversation_id: conversationId,
        message,
        connection_id: connectionId || null,
        route,
        ...responseOptions,
      }),
    }),
  getStage: (projectId) => request(`/api/projects/${projectId}/stage`),
  getWidgetData: (url) => request(url, { cache: "no-store", timeoutMs: 30000 }),
  putStage: (projectId, widgets) =>
    request(`/api/projects/${projectId}/stage`, {
      method: "PUT",
      body: JSON.stringify({ widgets }),
    }),
  addStageWidget: (projectId, widget) =>
    request(`/api/projects/${projectId}/stage/widgets`, {
      method: "POST",
      body: JSON.stringify(widget),
    }),
  patchStageWidget: (projectId, widgetId, patch) =>
    request(`/api/projects/${projectId}/stage/widgets/${widgetId}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),
  deleteStageWidget: (projectId, widgetId) =>
    request(`/api/projects/${projectId}/stage/widgets/${widgetId}`, {
      method: "DELETE",
    }),
  listConnections: () => request("/api/database-connections"),
  createConnection: (payload) =>
    request("/api/database-connections", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  listLocalModels: (baseUrl, apiKey) =>
    request("/api/ai/local-models", {
      method: "POST",
      body: JSON.stringify({ base_url: baseUrl, api_key: apiKey || "" }),
    }),
  testConnection: (id) =>
    request(`/api/database-connections/${id}/test`, { method: "POST" }),
  seedQuestions: (id, offset = 0) =>
    request(`/api/database-connections/${id}/questions/seed`, {
      method: "POST",
      timeoutMs: 300000,
      body: JSON.stringify({ offset }),
    }),
  listQuestions: (id) => request(`/api/database-connections/${id}/questions`),
  listTables: (id) => request(`/api/database-connections/${id}/tables`),
  getTablePermissions: (connectionId) =>
    request(`/api/table-permissions?connection_id=${encodeURIComponent(connectionId)}`),
  putTablePermissions: (payload) =>
    request("/api/table-permissions", {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
};
