import { beforeEach, test } from "node:test";
import assert from "node:assert/strict";
import { getAiSettings, setAiSettings } from "../src/aiSettings.js";

const values = new Map();
globalThis.localStorage = {
  getItem: (key) => values.get(key) ?? null,
  setItem: (key, value) => values.set(key, value),
};
beforeEach(() => values.clear());

test("legacy credentials remain in their original provider profile", () => {
  localStorage.setItem("sql2widget_ai_settings", JSON.stringify({ provider: "gemini", model: "saved-model", apiKey: "test-gemini-key" }));
  assert.equal(getAiSettings().model, "saved-model");
  assert.equal(getAiSettings("openai").apiKey, "");
  assert.equal(getAiSettings("local").apiKey, "");
  setAiSettings({ ...getAiSettings("local"), model: "installed-model" });
  assert.equal(getAiSettings().provider, "local");
  assert.equal(getAiSettings("gemini").apiKey, "test-gemini-key");
});

test("provider profiles keep separate models keys and URLs", () => {
  setAiSettings({ ...getAiSettings("openai"), model: "cloud-model", apiKey: "test-cloud-key" });
  setAiSettings({ ...getAiSettings("local"), model: "local-model", baseUrl: "http://local:1234/v1" });
  assert.equal(getAiSettings().baseUrl, "http://local:1234/v1");
  assert.equal(getAiSettings().apiKey, "");
  assert.equal(getAiSettings("openai").apiKey, "test-cloud-key");
  assert.equal(getAiSettings("openai").model, "cloud-model");
});

test("empty or corrupt storage does not override server settings", () => {
  assert.deepEqual(getAiSettings(), {});
  localStorage.setItem("sql2widget_ai_settings", "null");
  assert.deepEqual(getAiSettings(), {});
  localStorage.setItem("sql2widget_ai_settings", "invalid");
  assert.deepEqual(getAiSettings(), {});
});

test("retired Gemini model migrates without removing other profiles", () => {
  setAiSettings({ ...getAiSettings("local"), model: "local-model" });
  setAiSettings({ ...getAiSettings("gemini"), model: "gemini-2.5-flash", apiKey: "test-key" });
  assert.equal(getAiSettings().model, "gemini-3.6-flash");
  assert.equal(getAiSettings().apiKey, "test-key");
  assert.equal(getAiSettings("local").model, "local-model");
});
