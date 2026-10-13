export const EXTRA_COMPONENTS = [
  "CompareCard", "PivotTable", "StatusSummary", "EventTimeline", "KpiGroup", "DetailCard",
  "HorizontalBarChart", "ComboChart", "BoxPlot", "Treemap",
];
export const DISPLAY_KEYS = Object.fromEntries([
  "StackedBarChart", "Heatmap", "ScatterChart", "Histogram", "LineChart", ...EXTRA_COMPONENTS,
].map((component) => [component, ["xLabel", "yLabel"]]));
DISPLAY_KEYS.ComboChart.push("secondaryYLabel", "barLabel", "lineLabel");
DISPLAY_KEYS.CompareCard = ["currentLabel", "previousLabel"];
export const SQL_COMPONENTS = new Set([
  "KpiStat", "DataTable", "RankList", "BarChart", "LineChart", "PieChart", "KpiSparkline",
  "PieTable", "BarTable", "FilterBar", "StackedBarChart", "Heatmap", "ScatterChart", "Histogram",
  ...EXTRA_COMPONENTS,
]);
