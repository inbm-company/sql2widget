import assert from "node:assert/strict";
import test from "node:test";
import { graphSummary } from "../src/chatTrace.js";

test("missing history is never reported as graph unused", () => {
  assert.equal(graphSummary(null), "기록 없음");
  assert.equal(graphSummary({}), "기록 없음");
  assert.equal(graphSummary({ route: "schema_qa" }), "지식그래프 조회 안 함");
});

test("graph read, empty retrieval and context actually passed are distinct", () => {
  assert.equal(graphSummary({ knowledge: { entities_total: 0 } }), "지식그래프 조회 성공 · 결과 0개");
  assert.equal(graphSummary({ knowledge: { entities_total: 44, entities_in_prompt: 0 } }), "지식그래프 조회 성공 · 답변에 전달한 근거 없음");
  assert.equal(graphSummary({ knowledge: { entities_total: 44, entities_in_prompt: 12 } }), "지식그래프 사용 · 엔티티 12개 전달");
  assert.equal(graphSummary({ knowledge: { status: "no_project" } }), "지식그래프 조회 안 함 · 프로젝트 없음");
});

test("schema selection records graph failure and full-schema repair without implying graph answering", () => {
  assert.equal(graphSummary({ schema_link: { source: "full", reason: "graph_unavailable" } }), "지식그래프 조회 실패 · 전체 스키마 사용");
  assert.equal(graphSummary({ schema_link: { source: "graph" } }), "지식그래프로 테이블 선택");
  assert.equal(graphSummary({ schema_link: { source: "graph", escalated_to_full: true } }), "그래프로 테이블 선택 · 전체 스키마로 재시도");
  assert.equal(graphSummary({ schema_link: { source: "full", reason: "no_documented_tables" } }), "지식그래프 조회함 · 선택에 미사용");
});
