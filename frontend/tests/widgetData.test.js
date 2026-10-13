import { test } from "node:test";
import assert from "node:assert/strict";
import { widgetDefinition, widgetDataUrl } from "../src/widgets/widgetData.js";

test("copying a query widget carries SQL and original DB, without result arrays or KPI values", () => {
  const source = { widget_id: "w", component: "DataTable", sql: "SELECT * FROM orders",
    query_ref: { sql: "SELECT * FROM orders", connection_id: "northwind" },
    props: { rows: [{ value: 999 }], columns: [{ key: "value" }] } };
  const copied = widgetDefinition(source, "currently-selected-other-db");
  assert.deepEqual(copied.props, {});
  assert.equal(copied.query_ref.connection_id, "northwind");
  assert.ok(source.props.rows.length);
  assert.equal(widgetDefinition({ ...source, component: "KpiStat", props: { value: 999 } }).props.value, undefined);
});

test("analytical query definitions retain axis titles while removing observations and style inventions", () => {
  for (const component of ["StackedBarChart", "Heatmap", "ScatterChart", "Histogram"]) {
    const copied = widgetDefinition({ component, sql: "SELECT ...", props: {
      xLabel: "기준", yLabel: "금액", color: "red", cells: [{ value: 1 }], points: [], bins: [], categories: [],
    } });
    assert.deepEqual(copied.props, { xLabel: "기준", yLabel: "금액" });
  }
});

test("legacy query metadata is copied without snapshots, while static text stays inline", () => {
  const copied = widgetDefinition({ component: "BarChart", props: { __sql: "SELECT 1", categories: ["old"] } }, "sales");
  assert.deepEqual(copied.query_ref, { sql: "SELECT 1", connection_id: "sales" });
  assert.deepEqual(copied.props, {});
  const stored = widgetDefinition({ component: "BarChart", props: {
    __query_ref: { sql: "SELECT 1", connection_id: "sales" }, categories: ["old"],
  } });
  assert.deepEqual(stored.query_ref, copied.query_ref);
  const text = { component: "MarkdownBlock", props: { markdown: "설명" } };
  assert.deepEqual(widgetDefinition(text), text);
  assert.equal(widgetDataUrl(text, { projectId: "p" }), null);
});

test("data requests address owned saved widgets, never send browser SQL or the current DB choice", () => {
  const widget = { widget_id: "w/a", id: "s/a", sql: "SELECT secret FROM orders" };
  assert.equal(widgetDataUrl(widget, { conversationId: "c/a", projectId: "p" }),
    "/api/conversations/c%2Fa/widgets/w%2Fa/data");
  assert.equal(widgetDataUrl(widget, { projectId: "p/a" }), "/api/projects/p%2Fa/stage/widgets/s%2Fa/data");
  assert.equal(widgetDataUrl(widget), null);
  assert.equal(widgetDataUrl({ id: "legacy", component: "KpiStat", props: { value: 999 } }, { projectId: "p" }),
    "/api/projects/p/stage/widgets/legacy/data");
  assert.deepEqual(widgetDefinition({ component: "KpiStat", props: { value: 999 } }).props, {});
});
