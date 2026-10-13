import { test } from "node:test";
import assert from "node:assert/strict";
import { createChartScene } from "@tanstack/charts/scene";
import { renderChartSvg } from "@tanstack/charts/svg";
import { createHorizontalBarDefinition, createComboDefinition, createBoxPlotDefinition, createTreemapDefinition } from "../src/widgets/tanstackCatalogCharts.js";
import { tableRows, lineChartData } from "../src/widgets/tableData.js";
import { widgetDefinition, widgetDataUrl } from "../src/widgets/widgetData.js";
import { EXTRA_COMPONENTS } from "../src/widgets/catalogSettings.js";

test("table search, numeric sorting, and column filters compose without changing the fetched rows", () => {
  const rows = [{ region: "APAC", value: 20 }, { region: "EMEA", value: 3 }, { region: "APAC", value: 2 }];
  const before = structuredClone(rows);
  const columns = [{ key: "region" }, { key: "value" }];
  assert.deepEqual(tableRows(rows, columns, { filterKey: "region", filterValue: "APAC", sortKey: "value" }).map((r) => r.value), [2, 20]);
  assert.deepEqual(tableRows(rows, columns, { search: "emea", sortKey: "value", descending: true }), [rows[1]]);
  assert.deepEqual(tableRows(rows, columns, { search: "nothing" }), []);
  assert.deepEqual(rows, before);
});

test("line data preserves all series and gaps at different positions", () => {
  assert.deepEqual(lineChartData([{ points: [{ x: "1월", y: 3 }, { x: "2월", y: null }] },
    { points: [{ x: "2월", y: 5 }, { x: "3월", y: 6 }] }]), [
    { x: "1월", s0: 3 }, { x: "2월", s0: null, s1: 5 }, { x: "3월", s1: 6 },
  ]);
});

test("additional query definitions retain labels but never result snapshots", () => {
  for (const component of EXTRA_COMPONENTS) {
    const definition = widgetDefinition({ component, id: "widget", sql: "SELECT * FROM permitted",
      query_ref: { connection_id: "db", sql: "SELECT * FROM permitted" },
      props: { current: 500, rows: [1], nodes: [1], boxes: [1], fields: [1], items: [1], barLabel: "매출", lineLabel: "판매량" } });
    for (const key of ["current", "rows", "nodes", "boxes", "fields", "items"]) assert.equal(definition.props[key], undefined);
    assert.ok(widgetDataUrl(definition, { projectId: "project" }));
    if (component === "ComboChart") assert.deepEqual(definition.props, { barLabel: "매출", lineLabel: "판매량" });
  }
  const legacy = { component: "FilterBar", props: { filters: [{ label: "지역", value: "APAC" }] } };
  assert.deepEqual(widgetDefinition(legacy), legacy);
  assert.equal(widgetDataUrl(legacy, { projectId: "p" }), null);
});

test("combo metrics use distinct left and right numeric scales", () => {
  const scene = createChartScene(createComboDefinition({ points: [{ x: "1월", bar: 3000000, line: 30 }, { x: "2월", bar: 5000000, line: 50 }] }), { width: 600, height: 320 });
  assert.ok(scene.scales.y.domain[1] >= 5000000);
  assert.ok(scene.scales.secondaryY.domain[1] <= 100);
  assert.equal(scene.points.length, 4);
});

test("catalog charts handle empty input and preserve real box statistics, outliers and hierarchy", () => {
  const cases = [
    [createHorizontalBarDefinition, { categories: ["<script>", "B"], series: [{ data: [2, -3] }] }],
    [createComboDefinition, { points: [{ x: "1월", bar: 2, line: 3 }] }],
    [createBoxPlotDefinition, { boxes: [{ label: "A", minimum: 1, q1: 2, median: 3, q3: 4, maximum: 5, outliers: [8] }] }],
    [createTreemapDefinition, { nodes: [{ id: "root", parentId: null, label: "전체", value: 0 }, { id: "a", parentId: "root", group: "APAC", label: "A", value: 3 }, { id: "b", parentId: "root", group: "EMEA", label: "B", value: 2 }] }],
  ];
  for (const [create, props] of cases) {
    const before = structuredClone(props);
    for (const input of [{}, props]) {
      const scene = createChartScene(create(input), { width: 360, height: 200 });
      assert.doesNotMatch(renderChartSvg(scene, { ariaLabel: "차트" }), /NaN|Infinity|<script>/);
    }
    assert.deepEqual(props, before);
  }
  const box = createChartScene(createBoxPlotDefinition(cases[2][1]), { width: 480, height: 260 });
  assert.ok(box.points.some((point) => point.datum.value === 8));
  const tree = createChartScene(createTreemapDefinition(cases[3][1]), { width: 480, height: 260 });
  assert.deepEqual(tree.points.map((point) => point.datum.value).sort(), [2, 3]);
});
