import { barY } from "@tanstack/charts/bar";
import { cell, rect } from "@tanstack/charts/rect";
import { dot } from "@tanstack/charts/dot";
import { stack } from "@tanstack/charts/stack";
import { colorLegend, colorGradientLegend } from "@tanstack/charts/legend";
import { defineChart } from "@tanstack/charts/scene";
import { scaleBand } from "@tanstack/charts/scales/band";
import { scaleLinear } from "@tanstack/charts/scales/linear";
import { tooltip } from "@tanstack/charts/tooltip";

const ACCENT = "#0066cc";
const PALETTE = [ACCENT, "#0d9488", "#6366f1", "#64748b", "#0891b2", "#7c3aed"];
const THEME = {
  foreground: "#717171", muted: "#717171", grid: "#e8e8e8",
  background: "transparent", palette: PALETTE,
};
const GRID = { stroke: THEME.grid, strokeDasharray: "3 3", strokeOpacity: 1 };
const list = (value) => Array.isArray(value) ? value : [];
function number(value) {
  if (value == null || typeof value === "boolean" || value === "") return null;
  const result = Number(value);
  return Number.isFinite(result) ? result : null;
}
const linear = (label) => ({
  scale: scaleLinear, nice: true, grid: GRID,
  axis: { label, tickLabels: { fontSize: 11 } },
});
const band = (label) => ({
  scale: () => scaleBand().padding(0.15),
  axis: { label, tickLabels: { fontSize: 11 } },
});

export function createStackedBarDefinition(props) {
  const categories = list(props?.categories);
  const series = list(props?.series);
  const data = series.flatMap((entry, seriesIndex) => categories.map((category, index) => ({
    id: `${seriesIndex}:${index}`, category: String(index), label: String(category),
    series: String(entry.name ?? `시리즈 ${seriesIndex + 1}`), value: number(entry.data?.[index] ?? 0),
  }))).filter((row) => row.value !== null);
  return defineChart({
    marks: [barY(data, {
      x: "category", y: "value", z: "series", color: "series", key: "id",
      layout: stack({ offset: "diverging" }),
    })],
    scales: {
      x: {
        ...band(props?.xLabel),
        axis: {
          label: props?.xLabel,
          ticks: { format: (index) => String(categories[Number(index)] ?? "") },
          tickLabels: { fontSize: 11 },
        },
      },
      y: linear(props?.yLabel),
    },
    color: {
      domain: series.map((entry, i) => String(entry.name ?? `시리즈 ${i + 1}`)),
      range: PALETTE, legend: colorLegend({ placement: "bottom" }),
    },
    theme: THEME,
    tooltip: {
      use: tooltip,
      content: (points) => ({
        title: points[0]?.datum.label,
        rows: points.map((point) => ({
          label: point.datum.series, value: String(point.datum.value), color: point.color,
        })),
      }),
    },
  });
}

export function createHeatmapDefinition(props) {
  const data = list(props?.cells).filter((row) => row?.x != null && row?.y != null && number(row.value) !== null)
    .map((row, i) => ({ id: String(i), x: String(row.x), y: String(row.y), value: number(row.value) }));
  // A fixed blue intensity ramp; data controls values, never CSS or colors.
  const resolver = {
    id: "widget-heat-intensity",
    resolve: ({ values }) => {
      const min = values.length ? Math.min(...values) : 0;
      const max = values.length ? Math.max(...values) : 0;
      return {
        type: "configured", kind: "continuous", domain: [min, max], range: ["#edf4fc", ACCENT],
        map: (value) => {
          const t = max === min ? 1 : Math.max(0, Math.min(1, (value - min) / (max - min)));
          return `rgb(${Math.round(237 * (1 - t))},${Math.round(244 + (102 - 244) * t)},${Math.round(252 + (204 - 252) * t)})`;
        },
      };
    },
  };
  return defineChart({
    marks: [cell(data, { x: "x", y: "y", color: "value", key: "id", inset: 1 })],
    scales: { x: band(props?.xLabel), y: band(props?.yLabel) },
    color: {
      resolver,
      legend: data.length ? colorGradientLegend({ placement: "bottom" }) : undefined,
    },
    theme: THEME,
    tooltip: {
      use: tooltip,
      content: (points) => ({
        title: points[0] ? `${points[0].datum.x} · ${points[0].datum.y}` : undefined,
        rows: points.map((point) => ({
          label: "값", value: String(point.datum.value), color: point.color,
        })),
      }),
    },
  });
}

export function createScatterDefinition(props) {
  const data = list(props?.points).filter((point) => number(point?.x) !== null && number(point?.y) !== null)
    .map((point, i) => ({
      id: String(i), x: number(point.x), y: number(point.y),
      label: point.label == null ? undefined : String(point.label),
    }));
  return defineChart({
    marks: [dot(data, { x: "x", y: "y", key: "id", r: 4, fill: ACCENT })],
    scales: { x: linear(props?.xLabel), y: linear(props?.yLabel) },
    theme: THEME,
    tooltip: {
      use: tooltip,
      content: (points) => ({
        title: points[0]?.datum.label,
        rows: points.flatMap((point) => [
          { label: props?.xLabel || "X", value: String(point.datum.x) },
          { label: props?.yLabel || "Y", value: String(point.datum.y) },
        ]),
      }),
    },
  });
}

export function createHistogramDefinition(props) {
  const data = list(props?.bins).filter((bin) =>
    number(bin?.start) !== null && number(bin?.end) !== null && number(bin?.count) !== null
    && Number(bin.start) < Number(bin.end) && Number(bin.count) >= 0)
    .map((bin, i) => ({ id: String(i), start: number(bin.start), end: number(bin.end), count: number(bin.count) }));
  return defineChart({
    marks: [rect(data, {
      x: (bin) => bin.start / 2 + bin.end / 2, x1: "start", x2: "end",
      y: "count", y1: () => 0, y2: "count", key: "id", fill: ACCENT, inset: 0.5,
    })],
    scales: { x: linear(props?.xLabel || "값"), y: linear(props?.yLabel || "빈도") },
    theme: THEME,
    tooltip: {
      use: tooltip,
      content: (points) => ({
        title: points[0] ? `[${points[0].datum.start}, ${points[0].datum.end})` : undefined,
        rows: points.map((point) => ({
          label: props?.yLabel || "빈도", value: String(point.datum.count), color: ACCENT,
        })),
      }),
    },
  });
}
