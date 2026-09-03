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

function DataTable({ props }) {
  const columns = props?.columns || [];
  const rows = props?.rows || [];
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key}>{c.label || c.key}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, idx) => (
            <tr key={idx}>
              {columns.map((c) => (
                <td key={c.key}>{String(row[c.key] ?? "")}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
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
  const categories = props?.categories || [];
  const series = props?.series?.[0];
  const data = categories.map((c, i) => ({
    name: c,
    value: series?.data?.[i] ?? 0,
  }));
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
        <XAxis dataKey="name" stroke={MUTED} fontSize={12} />
        <YAxis stroke={MUTED} fontSize={12} allowDecimals={false} />
        <Tooltip />
        <Bar dataKey="value" fill={ACCENT} radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

function LineChartWidget({ props }) {
  const seriesList = props?.series || [];
  const points = seriesList[0]?.points || [];
  const data = points.map((p) => ({ name: p.x, value: p.y }));
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
        <XAxis dataKey="name" stroke={MUTED} fontSize={12} />
        <YAxis stroke={MUTED} fontSize={12} />
        <Tooltip />
        <Legend />
        <Line
          type="monotone"
          dataKey="value"
          name={seriesList[0]?.name || "value"}
          stroke={ACCENT}
          strokeWidth={2}
          dot={{ fill: INK, r: 3 }}
        />
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
