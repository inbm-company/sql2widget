import { barY } from "@tanstack/charts/bar";
import { defineChart } from "@tanstack/charts/scene";
import { scaleBand } from "@tanstack/charts/scales/band";
import { scaleLinear } from "@tanstack/charts/scales/linear";
import { tooltip } from "@tanstack/charts/tooltip";

const ACCENT = "#0066cc";
const MUTED = "#717171";
const GRID = "#e8e8e8";

// Preserve the existing BarChart props contract and first-series behavior.
export function createBarChartDefinition(props) {
  const categories = props?.categories || [];
  const series = props?.series?.[0];
  const data = categories.map((label, index) => {
    const value = Number(series?.data?.[index] ?? 0);
    return {
      // A separate band per row also preserves repeated category labels.
      id: String(index),
      label: String(label),
      value: Number.isFinite(value) ? value : null,
    };
  });
  const grid = { stroke: GRID, strokeDasharray: "3 3" };

  return defineChart({
    marks: [barY(data, { x: "id", y: "value", key: "id", fill: ACCENT, radius: { end: 4 } })],
    scales: {
      x: {
        scale: () => scaleBand().padding(0.2),
        grid,
        axis: {
          ticks: { format: (id) => data[Number(id)]?.label ?? "" },
          tickLabels: { fontSize: 12 },
        },
      },
      y: {
        scale: scaleLinear,
        nice: true,
        grid,
        axis: { tickLabels: { fontSize: 12 } },
      },
    },
    theme: { foreground: MUTED, muted: MUTED, grid: GRID, background: "transparent" },
    tooltip: {
      use: tooltip,
      content: (points) => ({
        title: points[0]?.datum.label,
        rows: points.map((point) => ({
          label: series?.name || "value",
          value: String(point.yValue),
          color: ACCENT,
        })),
      }),
    },
  });
}
