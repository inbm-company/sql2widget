const SETTINGS_KEY = "agent4any_ai_settings";

const DEFAULTS = {
  gemini: { model: "gemini-3.6-flash", baseUrl: "https://generativelanguage.googleapis.com/v1beta/openai", embeddingModel: "gemini-embedding-001" },
  openai: { model: "gpt-4o-mini", baseUrl: "https://api.openai.com/v1", embeddingModel: "text-embedding-3-small" },
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
  const saved = readSettings();
  localStorage.setItem(SETTINGS_KEY, JSON.stringify({
    provider: settings.provider,
    profiles: { ...saved.profiles, [settings.provider]: settings },
  }));
}
