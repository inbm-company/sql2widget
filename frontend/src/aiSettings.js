const SETTINGS_KEY = "sql2widget_ai_settings";

const DEFAULTS = {
  gemini: { model: "gemini-3.8-flash", baseUrl: "https://generativelanguage.googleapis.com/v1beta/openai", embeddingModel: "gemini-embedding-001" },
  openai: { model: "gpt-4o-mini", baseUrl: "https://api.openai.com/v1", embeddingModel: "text-embedding-3-small" },
  together: { model: "Qwen/Qwen3.5-9B", baseUrl: "https://api.together.ai/v1", embeddingModel: "" },
  local: { model: "", baseUrl: "http://host.docker.internal:11434/v1", embeddingModel: "" },
};

function readSettings() {
  try {
    const saved = JSON.parse(localStorage.getItem(SETTINGS_KEY) || "{}");
    if (!saved || typeof saved !== "object") return {};
    if (saved.profiles) return saved;
    // Keep existing single-provider credentials without copying them to other providers.
    return saved.provider ? { provider: saved.provider, profiles: { [saved.provider]: saved } } : {};
  } catch {
    return {};
  }
}

export function getJevApiKey() {
  const value = readSettings().jevApiKey;
  return typeof value === "string" ? value.trim() : "";
}

export function getAiSettings(provider) {
  const saved = readSettings();
  const name = provider || saved.provider;
  if (!DEFAULTS[name]) return {};
  const profile = { apiKey: "", ...DEFAULTS[name], ...saved.profiles?.[name], provider: name };
  if (name === "gemini" && profile.model === "gemini-2.5-flash") {
    profile.model = DEFAULTS.gemini.model;
    localStorage.setItem(SETTINGS_KEY, JSON.stringify({ ...saved,
      profiles: { ...saved.profiles, [name]: profile } }));
  }
  return profile;
}

export function setAiSettings(settings) {
  const { jevApiKey, ...profile } = settings;
  if (jevApiKey !== undefined && (typeof jevApiKey !== "string"
    || jevApiKey.trim().length > 8192 || /[\r\n]/.test(jevApiKey))) {
    throw new Error("Jev API key는 8,192자 이하의 한 줄 문자열이어야 합니다.");
  }
  const saved = readSettings();
  localStorage.setItem(SETTINGS_KEY, JSON.stringify({
    ...saved,
    provider: settings.provider,
    ...(jevApiKey !== undefined ? { jevApiKey: jevApiKey.trim() } : {}),
    profiles: { ...saved.profiles, [settings.provider]: profile },
  }));
}
