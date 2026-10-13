import { useMemo } from "react";
import { Chart } from "@tanstack/charts/react";
import { createBarChartDefinition } from "./tanstackBarChart.js";
import DataTable from "./DataTable.jsx";
import { CompareCard, KpiGroup, StatusSummary, EventTimeline, DetailCard } from "./CatalogCards.jsx";
import { createHorizontalBarDefinition, createComboDefinition, createBoxPlotDefinition, createTreemapDefinition } from "./tanstackCatalogCharts.js";
import { lineChartData } from "./tableData.js";
import {
  createStackedBarDefinition,
  createHeatmapDefinition,
  createScatterDefinition,
  createHistogramDefinition,
} from "./tanstackAnalyticalCharts.js";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  Pie,
  PieChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Legend,
} from "recharts";

const ACCENT = "#0066cc";
const INK = "#3c3c3c";
const MUTED = "#717171";
const GRID = "#e8e8e8";
const PALETTE = [ACCENT, "#0d9488", "#6366f1", "#64748b", "#0891b2", "#7c3aed"];

function KpiStat({ props }) {
  const { label, value, unit, delta } = props || {};
  return (
    <div className="kpi">
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">
        {value}
        {unit ? <span className="kpi-unit">{unit}</span> : null}
      </div>
      {delta != null ? <div className="kpi-delta">{delta}</div> : null}
    </div>
  );
}

function RankList({ props }) {
  const items = props?.items || [];
  return (
    <ol className="rank-list">
      {items.map((item) => (
        <li key={item.rank}>
          <span className="rank-num">{item.rank}</span>
          <span className="rank-label">{item.label}</span>
          <span className="rank-value">{item.value}</span>
          {item.meta ? <span className="rank-meta">{item.meta}</span> : null}
        </li>
      ))}
    </ol>
  );
}

function BarChartWidget({ props }) {
  const definition = useMemo(() => createBarChartDefinition(props), [props]);
  return (
    <Chart
      definition={definition}
      ariaLabel={props?.series?.[0]?.name || "막대 차트"}
      style={{ height: "100%", minWidth: 0, minHeight: 0, fontSize: 12 }}
    />
  );
}

function AnalyticalChart({ props, createDefinition, label, dataKey }) {
  const definition = useMemo(() => createDefinition(props), [props, createDefinition]);
  if (!props?.[dataKey]?.length) {
    return <div className="widget-empty">결과 없음</div>;
  }
  return (
    <Chart
      definition={definition}
      ariaLabel={label}
      style={{ height: "100%", minWidth: 0, minHeight: 0, fontSize: 12 }}
    />
  );
}

function LineChartWidget({ props }) {
  const seriesList = props?.series || [];
  const data = useMemo(() => lineChartData(seriesList), [seriesList]);
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
        <XAxis dataKey="x" stroke={MUTED} fontSize={12} />
        <YAxis stroke={MUTED} fontSize={12} />
        <Tooltip />
        <Legend />
        {seriesList.map((series, index) => <Line
          key={index}
          type="monotone"
          dataKey={`s${index}`}
          name={series.name || `시리즈 ${index + 1}`}
          stroke={PALETTE[index % PALETTE.length]}
          strokeWidth={2}
          dot={{ fill: INK, r: 3 }}
        />)}
      </LineChart>
    </ResponsiveContainer>
  );
}

function PieChartWidget({ props }) {
  const slices = props?.slices || [];
  return (
    <ResponsiveContainer width="100%" height="100%">
      <PieChart>
        <Pie data={slices} dataKey="value" nameKey="label" outerRadius="70%">
          {slices.map((_, i) => (
            <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
          ))}
        </Pie>
        <Tooltip />
        <Legend />
      </PieChart>
    </ResponsiveContainer>
  );
}

function Sparkline({ points }) {
  const data = (points || []).map((p) => ({ name: p.x, value: p.y }));
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data}>
        <Line
          type="monotone"
          dataKey="value"
          stroke={ACCENT}
          strokeWidth={2}
          dot={false}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

/** Number + sparkline — layout flips via container query */
function KpiSparkline({ props }) {
  const { label, value, unit, delta, points } = props || {};
  return (
    <div className="cq-composite">
      <div className="cq-composite__layout">
        <div className="cq-composite__primary cq-kpi-block">
          <div className="kpi-label">{label}</div>
          <div className="kpi-value">
            {value}
            {unit ? <span className="kpi-unit">{unit}</span> : null}
          </div>
          {delta != null ? <div className="kpi-delta">{delta}</div> : null}
        </div>
        <div className="cq-composite__secondary cq-spark-block">
          <Sparkline points={points} />
        </div>
      </div>
    </div>
  );
}

/** Bar + table (+ optional KPI header) — one widget, CQ layout */
function BarTable({ props }) {
  const {
    label,
    value,
    unit,
    delta,
    categories = [],
    series = [],
    columns,
    rows,
  } = props || {};
  const series0 = series[0];
  const chartData = categories.map((c, i) => ({
    name: c,
    value: series0?.data?.[i] ?? 0,
  }));
  const tableColumns = columns || [
    { key: "label", label: "항목" },
    { key: "value", label: "값" },
  ];
  const tableRows =
    rows ||
    categories.map((c, i) => ({
      label: c,
      value: series0?.data?.[i] ?? 0,
    }));

  return (
    <div className="cq-composite cq-bar-table">
      <div className="cq-composite__layout cq-bar-table__layout">
        <div className="cq-composite__primary cq-bar-block">
          {(label != null || value != null) && (
            <div className="cq-bar-header">
              {label ? <div className="kpi-label">{label}</div> : null}
              {value != null ? (
                <div className="kpi-value">
                  {value}
                  {unit ? <span className="kpi-unit">{unit}</span> : null}
                </div>
              ) : null}
              {delta != null ? <div className="kpi-delta">{delta}</div> : null}
            </div>
          )}
          <div className="cq-bar-chart">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
                <XAxis dataKey="name" stroke={MUTED} fontSize={11} />
                <YAxis stroke={MUTED} fontSize={11} allowDecimals={false} width={28} />
                <Tooltip />
                <Bar dataKey="value" fill={ACCENT} radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div className="cq-composite__secondary cq-table-block">
          <DataTable props={{ columns: tableColumns, rows: tableRows }} />
        </div>
      </div>
    </div>
  );
}

/** Pie + table — layout flips via container query */
function PieTable({ props }) {
  const slices = props?.slices || [];
  const columns = props?.columns || [
    { key: "label", label: "항목" },
    { key: "value", label: "값" },
  ];
  const rows =
    props?.rows ||
    slices.map((s) => ({
      label: s.label,
      value: s.value,
    }));

  return (
    <div className="cq-composite">
      <div className="cq-composite__layout">
        <div className="cq-composite__primary cq-pie-block">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={slices}
                dataKey="value"
                nameKey="label"
                innerRadius="42%"
                outerRadius="70%"
              >
                {slices.map((_, i) => (
                  <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="cq-composite__secondary cq-table-block">
          <DataTable props={{ columns, rows }} />
        </div>
      </div>
    </div>
  );
}

function MarkdownBlock({ props }) {
  const md = props?.markdown || "";
  return (
    <div className="markdown-block">
      {md.split("\n").map((line, i) => {
        if (line.startsWith("### ")) return <h4 key={i}>{line.slice(4)}</h4>;
        if (line.startsWith("## ")) return <h3 key={i}>{line.slice(3)}</h3>;
        if (line.startsWith("- ")) return <li key={i}>{line.slice(2)}</li>;
        if (!line.trim()) return <br key={i} />;
        return <p key={i}>{line}</p>;
      })}
    </div>
  );
}

function SourceList({ props }) {
  const sources = props?.sources || [];
  return (
    <ul className="source-list">
      {sources.map((s, i) => (
        <li key={i}>
          <strong>{s.title}</strong>
          {s.version ? <span> v{s.version}</span> : null}
          {s.section ? <span className="muted"> — {s.section}</span> : null}
        </li>
      ))}
    </ul>
  );
}

function FilterBar({ props }) {
  if (Array.isArray(props?.rows)) return <DataTable props={props} filterable />;
  const filters = props?.filters || [];
  return (
    <div className="filter-bar">
      {filters.map((f, i) => (
        <span key={i} className="filter-chip">
          {f.label}: {f.value}
        </span>
      ))}
    </div>
  );
}

const REGISTRY = {
  KpiStat,
  DataTable,
  RankList,
  BarChart: BarChartWidget,
  LineChart: LineChartWidget,
  PieChart: PieChartWidget,
  MarkdownBlock,
  SourceList,
  FilterBar,
  KpiSparkline,
  PieTable,
  BarTable,
  StackedBarChart: ({ props }) => <AnalyticalChart props={props} createDefinition={createStackedBarDefinition} label="누적 막대 차트" dataKey="categories" />,
  Heatmap: ({ props }) => <AnalyticalChart props={props} createDefinition={createHeatmapDefinition} label="히트맵" dataKey="cells" />,
  ScatterChart: ({ props }) => <AnalyticalChart props={props} createDefinition={createScatterDefinition} label="산점도" dataKey="points" />,
  Histogram: ({ props }) => <AnalyticalChart props={props} createDefinition={createHistogramDefinition} label="히스토그램" dataKey="bins" />,
  CompareCard,
  PivotTable: DataTable,
  StatusSummary,
  EventTimeline,
  KpiGroup,
  DetailCard,
  HorizontalBarChart: ({ props }) => <AnalyticalChart props={props} createDefinition={createHorizontalBarDefinition} label="가로 막대" dataKey="categories" />,
  ComboChart: ({ props }) => <AnalyticalChart props={props} createDefinition={createComboDefinition} label="막대와 선 복합 차트" dataKey="points" />,
  BoxPlot: ({ props }) => <AnalyticalChart props={props} createDefinition={createBoxPlotDefinition} label="박스플롯" dataKey="boxes" />,
  Treemap: ({ props }) => <AnalyticalChart props={props} createDefinition={createTreemapDefinition} label="트리맵" dataKey="nodes" />,
};

export default function WidgetRenderer({ component, props, compact = false }) {
  const Comp = REGISTRY[component];
  if (!Comp) {
    return <div className="widget-fallback">Unknown component: {component}</div>;
  }
  return (
    <div className={`widget-body ${compact ? "compact" : ""}`}>
      <Comp props={props} />
    </div>
  );
}
