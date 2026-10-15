import test from "node:test";
import assert from "node:assert/strict";
import { ROUTE_NAMES, routeSummary, stepQuestion } from "../src/chatTrace.js";

const first = "data_query";
const second = "general_chat";

test("returning to an earlier route retains both occurrences and their order", () => {
  const meta = { route: first, steps: [{ route: first }, { route: second }, { route: first }] };
  assert.equal(routeSummary(meta), `1. ${ROUTE_NAMES[first]} → 2. ${ROUTE_NAMES[second]} → 3. ${ROUTE_NAMES[first]}`);
});

test("different questions on one route remain separate steps", () => {
  assert.equal(routeSummary({route: first, steps: [{route: first}, {route: first}]}),
    `1. ${ROUTE_NAMES[first]} → 2. ${ROUTE_NAMES[first]}`);
});

test("an unknown execution route is not replaced with the plan or the previous route", () => {
  assert.equal(routeSummary({route: first, steps: [{route: first}, {expected_route: second}]}),
    `1. ${ROUTE_NAMES[first]} → 2. 경로 미기록`);
});

test("a replanned step shows its actual query instead of a different initial plan question", () => {
  const step = {route: first, expected_route: first, query: "재계획 후 실제 질문"};
  const meta = {plan: {replans: 1, steps: [{route: first, query: "처음 질문"}]}};
  assert.equal(stepQuestion(meta, step, 0), "재계획 후 실제 질문");
  assert.equal(stepQuestion(meta, {route: first}, 0), null);
});

test("legacy clarification is appended once and legacy single-route answers remain readable", () => {
  assert.equal(routeSummary({route: "clarify", steps: [{route: first}]}),
    `1. ${ROUTE_NAMES[first]} → 2. ${ROUTE_NAMES.clarify}`);
  assert.equal(routeSummary({route: "clarify", steps: [{route: "clarify"}]}), ROUTE_NAMES.clarify);
  assert.equal(routeSummary({route: first}), ROUTE_NAMES[first]);
});
