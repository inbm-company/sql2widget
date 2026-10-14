import { test } from "node:test";
import assert from "node:assert/strict";
import { assistantPresentation, chatTextBlocks } from "../src/chatText.js";

test("old explanations move into the body without mutating saved data or dropping real widgets", () => {
  const widget = { component: "DataTable", widget_id: "data", query_ref: { connection_id: "sales", sql: "SELECT 1" } };
  const artifact = { artifact_id: "old", widgets: [
    { component: "MarkdownBlock", title: "구조", props: { markdown: "컬럼 설명" } }, widget,
  ], choices: [{ route: "data_query" }] };
  const result = assistantPresentation("요약", artifact);
  assert.equal(result.content, "요약\n\n### 구조\n\n컬럼 설명");
  assert.deepEqual(result.artifact.widgets, [widget]);
  assert.equal(result.artifact.choices, artifact.choices);
  assert.equal(artifact.widgets.length, 2);
  assert.deepEqual(assistantPresentation("본문", null), { content: "본문", artifact: null });
});

test("text-only historical artifacts and empty artifacts have no display widgets", () => {
  const result = assistantPresentation("", { artifact_id: "old", widgets: [
    { component: "MarkdownBlock", title: "구조", props: { markdown: "## orders\n설명" } },
  ] });
  assert.equal(result.content, "## orders\n설명");
  assert.deepEqual(result.artifact.widgets, []);
  assert.deepEqual(assistantPresentation("본문", { artifact_id: "empty" }).artifact.widgets, []);
});

test("table sections are rendered as independent body tables, retaining escaped pipes", () => {
  const blocks = chatTextBlocks("## orders\r\n주문입니다.\r\n\r\n| 컬럼 | 설명 |\r\n| :--- | ---: |\r\n| `id` | A\\|B |\r\n\r\n## products\r\n이름 | 타입\r\n--- | ---\r\nname | text");
  assert.deepEqual(blocks.map((block) => block.type), ["heading", "paragraph", "table", "heading", "table"]);
  assert.deepEqual(blocks[2].rows, [["`id`", "A|B"]]);
  assert.deepEqual(blocks[4], { type: "table", columns: ["이름", "타입"], rows: [["name", "text"]] });
});

test("code and unsupported or malformed markup stay readable text", () => {
  const source = "```sql\n| id | type |\n| --- | --- |\n```\n\n<script>alert(1)</script>\n\n| A | B |\n| --- |\n\n- 설명\n- 다음 설명\n\n1. 첫 단계\n2. 다음 단계";
  const blocks = chatTextBlocks(source);
  assert.equal(blocks[0].type, "code");
  assert.ok(blocks[0].text.includes("| --- | --- |"));
  assert.deepEqual(blocks[1], { type: "paragraph", text: "<script>alert(1)</script>" });
  assert.equal(blocks[2].type, "paragraph");
  assert.deepEqual(blocks[3], { type: "list", ordered: false, items: ["설명", "다음 설명"] });
  assert.equal(blocks[4].ordered, true);
});
