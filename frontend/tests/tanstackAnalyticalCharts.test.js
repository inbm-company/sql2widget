import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createChartScene } from "@tanstack/charts/scene";
import { renderChartSvg } from "@tanstack/charts/svg";
import { createStackedBarDefinition, createHeatmapDefinition, createScatterDefinition, createHistogramDefinition } from "../src/widgets/tanstackAnalyticalCharts.js";
import { canShowSql, resolveWidgetSql } from "../src/sqlHelpers.js";

const scene = (definition, width = 480, height = 260) => createChartScene(definition, { width, height });

test("stacked bars preserve every series, sum positive segments, and separate negative segments", () => {
  const chart = scene(createStackedBarDefinition({ categories: ["서울", "서울"], series: [
    { name: "A", data: [3, -2] }, { name: "B", data: [2, 4] },
  ] }));
  assert.equal(chart.points.length, 4);
  assert.deepEqual(chart.colors.domain, ["A", "B"]);
  assert.notEqual(chart.colors.map("A"), chart.colors.map("B"));
  assert.ok(chart.scales.y.domain[0] <= -2 && chart.scales.y.domain[1] >= 5);
  assert.notEqual(chart.points[0].x, chart.points[1].x);
  assert.equal(chart.points[0].x, chart.points[2].x);
});

test("heat intensity follows numeric magnitude rather than encounter order and handles constant values", () => {
  const chart = scene(createHeatmapDefinition({ cells: [
    { x: "A", y: "B", value: 10 }, { x: "C", y: "C", value: -2 }, { x: "D", y: "B", value: 0 },
  ] }));
  assert.deepEqual(chart.colors.domain, [-2, 10]);
  assert.notEqual(chart.colors.map(-2), chart.colors.map(10));
  assert.ok(chart.points[0].y < chart.points[1].y);
  const constant = scene(createHeatmapDefinition({ cells: [{ x: "A", y: "B", value: 5 }] }));
  assert.doesNotMatch(renderChartSvg(constant, { ariaLabel: "히트맵" }), /NaN|Infinity/);
});

test("scatter observations keep numeric coordinates, repeated pairs, and tooltip labels", () => {
  const definition = createScatterDefinition({ xLabel: "점수", yLabel: "공격량", points: [
    { x: "1.5", y: -2, label: "서버 A" }, { x: 1.5, y: -2 }, { x: null, y: 2 },
  ] });
  const chart = scene(definition);
  assert.equal(chart.points.length, 2);
  assert.deepEqual(chart.points.map((p) => [p.xValue, p.yValue]), [[1.5, -2], [1.5, -2]]);
  assert.deepEqual(definition.tooltip.content([chart.points[0]]), {
    title: "서버 A", rows: [{ label: "점수", value: "1.5" }, { label: "공격량", value: "-2" }],
  });
});

test("histogram uses numeric interval widths and includes zero-count bins", () => {
  const definition = createHistogramDefinition({ bins: [
    { start: -10, end: 0, count: 2 }, { start: 0, end: 20, count: 4 }, { start: 20, end: 30, count: 0 },
  ] });
  const chart = scene(definition);
  assert.deepEqual(chart.scales.x.domain, [-10, 30]);
  assert.equal(chart.points.length, 3);
  const wide = chart.scales.x.map(20) - chart.scales.x.map(0);
  const narrow = chart.scales.x.map(0) - chart.scales.x.map(-10);
  assert.ok(Math.abs(wide - 2 * narrow) < 1e-9);
  assert.deepEqual(definition.tooltip.content([chart.points[0]]).title, "[-10, 0)");
});

test("all additional chart definitions render empty data and resize without mutating props", () => {
  const cases = [
    [createStackedBarDefinition, { categories: ["<script>"], series: [{ name: "매출", data: [3] }] }],
    [createHeatmapDefinition, { cells: [{ x: "<script>", y: "B", value: 3 }] }],
    [createScatterDefinition, { points: [{ x: 1, y: 3 }] }],
    [createHistogramDefinition, { bins: [{ start: 0, end: 1, count: 3 }] }],
  ];
  for (const [create, props] of cases) {
    const before = structuredClone(props);
    for (const input of [undefined, {}, props]) {
      const definition = create(input);
      for (const [width, height] of [[300, 164], [720, 420]]) {
        const svg = renderChartSvg(scene(definition, width, height), { ariaLabel: "테스트" });
        assert.doesNotMatch(svg, /NaN|Infinity|<script>/);
        assert.match(svg, new RegExp(`viewBox="0 0 ${width} ${height}"`));
      }
    }
    assert.deepEqual(props, before);
  }
});

test("the server catalog, frontend registry, schema prompt, and documented catalog agree", () => {
  const read = (path) => readFileSync(new URL(path, import.meta.url), "utf8");
  const config = read("../../backend/app/config.py").split("ALLOWED_COMPONENTS =")[1];
  const server = [...config.matchAll(/"(\w+)"/g)].map((m) => m[1]).sort();
  const registry = read("../src/widgets/WidgetRenderer.jsx").split("const REGISTRY = {")[1].split("\n};")[0];
  const frontend = [...registry.matchAll(/^  (\w+)(?:,|:)/gm)].map((m) => m[1]).sort();
  const prompt = read("../../backend/app/prompts.py").match(/"component": "([^"]+)"/)[1].split("|").sort();
  const catalog = read("../../docs/features/widgets-artifact.md").split("## 허용 위젯 카탈로그")[1].split("### TanStack")[0];
  const documented = [...catalog.matchAll(/^\| `(\w+)` \|/gm)].map((m) => m[1]).sort();
  assert.equal(server.length, 16);
  assert.deepEqual(frontend, server);
  assert.deepEqual(prompt, server);
  assert.deepEqual(documented, server);
  for (const component of ["StackedBarChart", "Heatmap", "ScatterChart", "Histogram"]) {
    assert.ok(canShowSql({ component }));
    assert.equal(resolveWidgetSql({ component }), "");
    assert.equal(resolveWidgetSql({ component, sql: "SELECT 1" }), "SELECT 1");
  }
});
