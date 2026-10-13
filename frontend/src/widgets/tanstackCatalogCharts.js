import { barX, barY } from "@tanstack/charts/bar";
import { lineY } from "@tanstack/charts/line";
import { rect } from "@tanstack/charts/rect";
import { link } from "@tanstack/charts/link";
import { dot } from "@tanstack/charts/dot";
import { treemap } from "@tanstack/charts/hierarchy/treemap";
import { defineChart } from "@tanstack/charts/scene";
import { scaleLinear } from "@tanstack/charts/scales/linear";
import { scaleBand } from "@tanstack/charts/scales/band";
import { tooltip } from "@tanstack/charts/tooltip";
import { colorLegend } from "@tanstack/charts/legend";

const ACCENT = "#0066cc";
const SECONDARY = "#0d9488";
const PALETTE = [ACCENT, SECONDARY, "#6366f1", "#64748b", "#0891b2", "#7c3aed"];
const theme = { foreground: "#717171", muted: "#717171", grid: "#e8e8e8", background: "transparent", palette: PALETTE };
const linear = (label) => ({ scale: scaleLinear, nice: true, grid: { stroke: theme.grid, strokeDasharray: "3 3" }, axis: { label, tickLabels: { fontSize: 11 } } });
const band = (label, data, key = "label") => ({
  scale: () => scaleBand().padding(0.35),
  axis: { label, ticks: { format: (id) => data[Number(id)]?.[key] ?? "" }, tickLabels: { fontSize: 11 } },
});

export function createHorizontalBarDefinition(props) {
  const data = (props?.categories || []).map((label, i) => ({ id: String(i), label: String(label), value: props?.series?.[0]?.data?.[i] ?? 0 }));
  return defineChart({
    marks: [barX(data, { y: "id", x: "value", key: "id", fill: ACCENT, radius: { end: 3 } })],
    scales: { x: linear(props?.xLabel), y: band(props?.yLabel, data) },
    theme,
    tooltip: { use: tooltip, content: (points) => ({ title: points[0]?.datum.label,
      rows: points.map((point) => ({ label: props?.xLabel || "값", value: String(point.datum.value), color: ACCENT })) }) },
  });
}

export function createComboDefinition(props) {
  const data = (props?.points || []).map((point, i) => ({ ...point, id: String(i) }));
  const barLabel = props?.barLabel || "막대";
  const lineLabel = props?.lineLabel || "선";
  return defineChart({
    marks: [
      barY(data, { x: "id", y: "bar", color: () => barLabel, key: "id", fill: ACCENT }),
      lineY(data, { x: "id", y: "line", yScale: "secondaryY", color: () => lineLabel, key: "id", stroke: SECONDARY, strokeWidth: 2, points: true }),
    ],
    scales: {
      x: band(props?.xLabel, data, "x"),
      y: linear(props?.yLabel || barLabel),
      secondaryY: { ...linear(props?.secondaryYLabel || lineLabel), channel: "y", side: "right", grid: false },
    },
    color: { domain: [barLabel, lineLabel], range: [ACCENT, SECONDARY], legend: colorLegend() },
    theme,
    tooltip: { use: tooltip, content: (points) => ({ title: points[0]?.datum.x,
      rows: points[0] ? [
        { label: barLabel, value: points[0].datum.bar == null ? "—" : String(points[0].datum.bar), color: ACCENT },
        { label: lineLabel, value: points[0].datum.line == null ? "—" : String(points[0].datum.line), color: SECONDARY },
      ] : [] }) },
  });
}

export function createBoxPlotDefinition(props) {
  const data = (props?.boxes || []).map((box, i) => ({ ...box, id: String(i) }));
  const outliers = data.flatMap((box) => (box.outliers || []).map((value, i) => ({ ...box, value, key: `${box.id}:${i}` })));
  const caps = (field, id, width) => rect(data, { id, x: "id", y: field, y1: field, y2: field,
    key: "id", fill: "none", stroke: ACCENT, strokeWidth: width, inset: 0 });
  return defineChart({
    marks: [
      link(data, { x1: "id", x2: "id", y1: "minimum", y2: "maximum", key: "id", stroke: ACCENT }),
      rect(data, { id: "quartile", x: "id", y: "median", y1: "q1", y2: "q3", key: "id", fill: ACCENT, fillOpacity: 0.2, stroke: ACCENT }),
      caps("minimum", "lower-whisker", 1), caps("maximum", "upper-whisker", 1), caps("median", "median", 2),
      dot(outliers, { x: "id", y: "value", key: "key", fill: ACCENT, r: 3 }),
    ],
    scales: { x: band(props?.xLabel, data), y: linear(props?.yLabel) },
    theme,
    tooltip: { use: tooltip, content: (points) => ({ title: points[0]?.datum.label,
      rows: points[0] ? [
        { label: "하한 수염", value: String(points[0].datum.minimum) },
        { label: "1사분위", value: String(points[0].datum.q1) },
        { label: "중앙값", value: String(points[0].datum.median) },
        { label: "3사분위", value: String(points[0].datum.q3) },
        { label: "상한 수염", value: String(points[0].datum.maximum) },
        ...(points[0].datum.value != null ? [{ label: "이상치", value: String(points[0].datum.value) }] : []),
      ] : [] }) },
  });
}

export function createTreemapDefinition(props) {
  const nodes = props?.nodes || [];
  return defineChart({
    marks: nodes.length ? [treemap(nodes, {
      nodeId: "id", parentId: "parentId", value: "value",
      color: (node) => node.data?.group,
      label: (node) => node.data?.label, labelFill: "#ffffff", labelFontSize: 11,
      paddingInner: 2, paddingOuter: 3,
    })] : [],
    scales: { x: { scale: scaleLinear }, y: { scale: scaleLinear } }, guides: false, theme,
    color: { range: PALETTE, legend: colorLegend() },
    tooltip: { use: tooltip, content: (points) => ({ title: points[0]?.datum.data?.label,
      rows: points[0] ? [{ label: points[0].datum.data?.group || "값", value: String(points[0].datum.value), color: points[0].color }] : [] }) },
  });
}
