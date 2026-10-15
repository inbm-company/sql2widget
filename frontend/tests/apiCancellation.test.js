import { afterEach, test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const settingsUrl = new URL("../src/aiSettings.js", import.meta.url).href;
const source = (await readFile(new URL("../src/api.js", import.meta.url), "utf8"))
  .replace("import.meta.env.VITE_API_BASE", '""')
  .replaceAll('"./aiSettings"', JSON.stringify(settingsUrl));
const { api } = await import("data:text/javascript;base64," + Buffer.from(source).toString("base64"));
const originalFetch = globalThis.fetch;
const originalSetTimeout = globalThis.setTimeout;
const originalClearTimeout = globalThis.clearTimeout;
globalThis.localStorage = { getItem: () => null };
afterEach(() => {
  globalThis.fetch = originalFetch;
  globalThis.setTimeout = originalSetTimeout;
  globalThis.clearTimeout = originalClearTimeout;
});

const chat = (signal) => api.chat("conversation", "question", null, null, signal);

function waitForAbort(signal) {
  return new Promise((resolve, reject) => {
    if (signal.aborted) reject(signal.reason);
    else signal.addEventListener("abort", () => reject(signal.reason), { once: true });
  });
}

test("stop cancels fetch and remains AbortError instead of a timeout", async () => {
  const controller = new AbortController();
  globalThis.fetch = (url, options) => waitForAbort(options.signal);
  const pending = chat(controller.signal);
  controller.abort();
  await assert.rejects(pending, (err) => err === controller.signal.reason && err.name === "AbortError");
});

test("stop also cancels a response body after headers arrive", async () => {
  const controller = new AbortController();
  let bodyStarted;
  const started = new Promise((resolve) => { bodyStarted = resolve; });
  globalThis.fetch = async (url, { signal }) => ({
    ok: true, status: 200,
    json: () => { bodyStarted(); return waitForAbort(signal); },
  });
  const pending = chat(controller.signal);
  await started;
  controller.abort();
  await assert.rejects(pending, (err) => err === controller.signal.reason);
});

test("request timeout remains active when a caller signal is supplied", async () => {
  let expire;
  let cleared = false;
  globalThis.setTimeout = (callback) => { expire = callback; return 123; };
  globalThis.clearTimeout = (id) => { cleared = id === 123; };
  globalThis.fetch = (url, options) => waitForAbort(options.signal);
  const controller = new AbortController();
  const pending = chat(controller.signal);
  expire();
  await assert.rejects(pending, /Request timed out: \/api\/chat/);
  assert.equal(controller.signal.aborted, false);
  assert.equal(cleared, true);
});

test("an already stopped request cannot proceed", async () => {
  const controller = new AbortController();
  controller.abort();
  globalThis.fetch = (url, { signal }) => {
    assert.equal(signal.aborted, true);
    return waitForAbort(signal);
  };
  await assert.rejects(chat(controller.signal), (err) => err === controller.signal.reason);
});
