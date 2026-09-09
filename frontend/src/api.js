const API_BASE = import.meta.env.VITE_API_BASE ?? "";

const TOKEN_KEY = "agent4any_access";
const REFRESH_KEY = "agent4any_refresh";
const AI_SETTINGS_KEY = "agent4any_ai_settings";

export function getAiSettings() {
  try { return JSON.parse(localStorage.getItem(AI_SETTINGS_KEY) || "{}"); } catch { return {}; }
}

export function setAiSettings(settings) {
  localStorage.setItem(AI_SETTINGS_KEY, JSON.stringify(settings));
}

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
    const ai = getAiSettings();
    if (ai.apiKey) headers["X-LLM-API-Key"] = ai.apiKey;
    if (ai.provider) headers["X-LLM-Provider"] = ai.provider;
    if (ai.model) headers["X-LLM-Model"] = ai.model;
  }

  const controller = new AbortController();
  const timeoutMs = options.timeoutMs ?? 15000;
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let res;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers,
      signal: options.signal || controller.signal,
    });
  } catch (err) {
    if (err?.name === "AbortError") {
      const timeoutErr = new Error(`Request timed out: ${path}`);
      timeoutErr.status = 0;
      throw timeoutErr;
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }

  if (res.status === 401 && retry && getRefreshToken() && !path.includes("/auth/")) {
    await refreshAccessToken();
    return request(path, options, { retry: false });
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      /* ignore */
    }
    const err = new Error(detail);
    err.status = res.status;
    throw err;
  }

  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  login: (email, password) =>
    request("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  me: () => request("/api/auth/me"),
  listConversations: () => request("/api/conversations"),
  createConversation: (title) =>
    request("/api/conversations", {
      method: "POST",
      body: JSON.stringify({ title }),
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
  chat: (conversationId, message, connectionId) =>
    request("/api/chat", {
      method: "POST",
      body: JSON.stringify({
        conversation_id: conversationId,
        message,
        connection_id: connectionId || null,
      }),
    }),
  getStage: (conversationId) =>
    request(`/api/conversations/${conversationId}/stage`),
  putStage: (conversationId, widgets) =>
    request(`/api/conversations/${conversationId}/stage`, {
      method: "PUT",
      body: JSON.stringify({ widgets }),
    }),
  addStageWidget: (conversationId, widget) =>
    request(`/api/conversations/${conversationId}/stage/widgets`, {
      method: "POST",
      body: JSON.stringify(widget),
    }),
  patchStageWidget: (conversationId, widgetId, patch) =>
    request(`/api/conversations/${conversationId}/stage/widgets/${widgetId}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),
  deleteStageWidget: (conversationId, widgetId) =>
    request(`/api/conversations/${conversationId}/stage/widgets/${widgetId}`, {
      method: "DELETE",
    }),
  listConnections: () => request("/api/database-connections"),
  createConnection: (payload) =>
    request("/api/database-connections", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  testConnection: (id) =>
    request(`/api/database-connections/${id}/test`, { method: "POST" }),
  listTables: (id) => request(`/api/database-connections/${id}/tables`),
  getTablePermissions: (connectionId) =>
    request(`/api/table-permissions?connection_id=${encodeURIComponent(connectionId)}`),
  putTablePermissions: (payload) =>
    request("/api/table-permissions", {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
};
