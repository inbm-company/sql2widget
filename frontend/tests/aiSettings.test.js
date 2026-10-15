import { beforeEach, test } from "node:test";
import assert from "node:assert/strict";
import { getAiSettings, getJevApiKey, setAiSettings } from "../src/aiSettings.js";

const values = new Map();
globalThis.localStorage = {
  getItem: (key) => values.get(key) ?? null,
  setItem: (key, value) => values.set(key, value),
};
beforeEach(() => values.clear());

test("Together has an independent profile and preserves saved providers and the shared Jev key", () => {
  setAiSettings({ ...getAiSettings("gemini"), apiKey: "test-gemini", jevApiKey: "test-jev" });
  setAiSettings({ ...getAiSettings("openai"), apiKey: "test-openai", model: "saved-model" });
  const together = getAiSettings("together");
  assert.equal(together.model, "Qwen/Qwen3.5-9B");
  assert.equal(together.baseUrl, "https://api.together.ai/v1");
  assert.equal(together.apiKey, "");
  assert.equal(together.embeddingModel, "");
  setAiSettings({ ...together, apiKey: "test-together", model: "dedicated-chat" });
  assert.equal(getAiSettings().provider, "together");
  assert.equal(getAiSettings().model, "dedicated-chat");
  assert.equal(getAiSettings("gemini").apiKey, "test-gemini");
  assert.equal(getAiSettings("openai").apiKey, "test-openai");
  assert.equal(getAiSettings("openai").model, "saved-model");
  assert.equal(getJevApiKey(), "test-jev");
});
