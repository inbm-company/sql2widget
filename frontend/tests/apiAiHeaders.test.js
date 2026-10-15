import { beforeEach, test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { getAiSettings, setAiSettings } from "../src/aiSettings.js";

// Vite supplies import.meta.env and resolves extensionless imports in the app.
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


test("Together settings reach AI requests without sending another provider's credentials", async () => {
  setAiSettings({ ...getAiSettings("openai"), apiKey: "test-openai" });
  setAiSettings({ ...getAiSettings("together"), apiKey: "test-together" });
  await api.chat("conversation", "question", "connection");
  await api.seedQuestions("connection");
  for (const { headers } of requests) {
    assert.equal(headers["X-LLM-Provider"], "together");
    assert.equal(headers["X-LLM-API-Key"], "test-together");
    assert.equal(headers["X-LLM-Model"], "Qwen/Qwen3.5-9B");
    assert.equal(headers["X-LLM-Base-URL"], "https://api.together.ai/v1");
    assert.ok(!("X-LLM-Embedding-Model" in headers));
  }
});
