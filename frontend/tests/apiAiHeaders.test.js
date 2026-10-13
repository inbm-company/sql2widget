import { beforeEach, test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { getAiSettings, setAiSettings } from "../src/aiSettings.js";

// Vite provides import.meta.env and resolves the app's extensionless imports.
const settingsUrl = new URL("../src/aiSettings.js", import.meta.url).href;
const source = (await readFile(new URL("../src/api.js", import.meta.url), "utf8"))
  .replace("import.meta.env.VITE_API_BASE", '""')
  .replaceAll('"./aiSettings"', JSON.stringify(settingsUrl));
const { api } = await import("data:text/javascript;base64," + Buffer.from(source).toString("base64"));
const saved = new Map();
const requests = [];
globalThis.localStorage = {
  getItem: (key) => saved.get(key) ?? null,
  setItem: (key, value) => saved.set(key, value),
  removeItem: (key) => saved.delete(key),
};
globalThis.fetch = async (url, options) => {
  requests.push({ url, ...options });
  return { ok: true, status: 200, json: async () => ({}) };
};
beforeEach(() => { saved.clear(); requests.length = 0; });

test("widget data fetches send authentication only and bypass HTTP caches", async () => {
  saved.set("sql2widget_access", "test-access");
  setAiSettings({ provider: "openai", apiKey: "llm-test", jevApiKey: "routing-test" });
  await api.getWidgetData("/api/projects/p/stage/widgets/w/data");
  assert.equal(requests[0].headers.Authorization, "Bearer test-access");
  assert.equal(requests[0].headers["X-LLM-API-Key"], undefined);
  assert.equal(requests[0].headers["X-Jev-API-Key"], undefined);
  assert.equal(requests[0].cache, "no-store");
  assert.equal(requests[0].body, undefined);
});

test("chat alone sends the shared Jev key after switching model providers", async () => {
  setAiSettings({ provider: "gemini", apiKey: "gemini-test", jevApiKey: "routing-test" });
  setAiSettings({ provider: "openai", apiKey: "openai-test" });
  await api.chat("chat", "주문 수", "sales");
  await api.listConnections();
  await api.seedQuestions("sales", 0);
  await api.listLocalModels("http://localhost:11434/v1", "local-test");
  assert.equal(requests[0].headers["X-Jev-API-Key"], "routing-test");
  assert.equal(requests[0].headers["X-LLM-API-Key"], "openai-test");
  assert.ok(requests.every(({ body }) => !body?.includes("routing-test")));
  assert.ok(requests.slice(1).every(({ headers }) => !("X-Jev-API-Key" in headers)));
});

test("clearing the Jev key stops sending the header", async () => {
  setAiSettings({ provider: "openai", jevApiKey: "routing-test" });
  await api.chat("chat", "주문 수", "sales");
  setAiSettings({ ...getAiSettings(), jevApiKey: "" });
  await api.chat("chat", "고객 수", "sales");
  assert.equal(requests[0].headers["X-Jev-API-Key"], "routing-test");
  assert.ok(!("X-Jev-API-Key" in requests[1].headers));
});
