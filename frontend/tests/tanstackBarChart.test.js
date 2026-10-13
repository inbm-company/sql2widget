import { test } from "node:test";
import assert from "node:assert/strict";
import { createChartScene } from "@tanstack/charts/scene";
import { renderChartSvg } from "@tanstack/charts/svg";
import { createBarChartDefinition } from "../src/widgets/tanstackBarChart.js";

test("duplicate categories keep separate bars and the first series keeps its values", () => {
  const props = {
    categories: ["서울", "서울", "부산"],
    series: [{ name: "매출", data: [12.5, 0, -3] }, { name: "다른 값", data: [99, 99, 99] }],
  };
  const before = structuredClone(props);
  const definition = createBarChartDefinition(props);
  const scene = createChartScene(definition, { width: 480, height: 180 });
  assert.deepEqual(scene.points.map((point) => point.yValue), [12.5, 0, -3]);
  assert.equal(new Set(scene.points.map((point) => point.x)).size, 3);
  assert.deepEqual(definition.tooltip.content([scene.points[0]]), {
    title: "서울", rows: [{ label: "매출", value: "12.5", color: "#0066cc" }],
  });
  assert.deepEqual(props, before);
});

test("empty, absent, and missing series values render without invalid SVG geometry", () => {
  for (const props of [undefined, {}, { categories: [], series: [] }, { categories: ["항목"] }]) {
    const scene = createChartScene(createBarChartDefinition(props), { width: 300, height: 164 });
    const svg = renderChartSvg(scene, { ariaLabel: "막대 차트" });
    assert.doesNotMatch(svg, /NaN|Infinity/);
    assert.equal(scene.points.length, props?.categories?.length || 0);
    if (scene.points.length) assert.equal(scene.points[0].yValue, 0);
  }
});

test("numeric strings retain their values and nonnumeric values are omitted", () => {
  const scene = createChartScene(createBarChartDefinition({
    categories: ["정상", "잘못된 값", "음수"],
    series: [{ data: ["4.25", "invalid", "-1"] }],
  }), { width: 400, height: 180 });
  assert.deepEqual(scene.points.map((point) => point.yValue), [4.25, -1]);
  assert.doesNotMatch(renderChartSvg(scene, { ariaLabel: "막대 차트" }), /NaN|Infinity/);
});

test("the same definition fits preview and resized Stage dimensions and escapes labels", () => {
  const definition = createBarChartDefinition({
    categories: ["<script>alert(1)</script>", "Global Sales"],
    series: [{ data: [5, 10] }],
  });
  const small = createChartScene(definition, { width: 320, height: 164 });
  const large = createChartScene(definition, { width: 720, height: 420 });
  assert.ok(large.points[1].x > small.points[1].x);
  assert.deepEqual(large.points.map((point) => point.yValue), small.points.map((point) => point.yValue));
  const svg = renderChartSvg(large, { ariaLabel: "막대 차트" });
  assert.match(svg, /viewBox="0 0 720 420"/);
  assert.doesNotMatch(svg, /<script>/);
  assert.match(svg, /&lt;script&gt;/);
});
