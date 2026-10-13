const format = (value) => value == null ? "—" : typeof value === "number"
  ? value.toLocaleString("ko-KR", { maximumFractionDigits: 2 })
  : typeof value === "object" ? JSON.stringify(value) : String(value);

export function CompareCard({ props }) {
  return <div className="catalog-card compare-card">
    <div className="kpi-label">{props?.label}</div>
    <div className="compare-values">
      <div><span>{props?.currentLabel || "현재"}</span><strong>{format(props?.current)} {props?.unit || ""}</strong></div>
      <div><span>{props?.previousLabel || "이전"}</span><strong>{format(props?.previous)} {props?.unit || ""}</strong></div>
    </div>
    <div className="compare-change">증감 {props?.delta > 0 ? "+" : ""}{format(props?.delta)} {props?.unit || ""}
      <span>{props?.changeRate == null ? "증감률 계산 불가" : `${props.changeRate > 0 ? "+" : ""}${format(props.changeRate)}%`}</span>
    </div>
  </div>;
}

export function KpiGroup({ props }) {
  const items = props?.items || [];
  return <div className="catalog-card kpi-group">{items.length ? items.map((item, i) =>
    <div key={i}><div className="kpi-label">{item.label}</div><div className="kpi-value">{format(item.value)}<span className="kpi-unit">{item.unit}</span></div></div>
  ) : <div className="widget-empty">결과 없음</div>}</div>;
}

export function StatusSummary({ props }) {
  const items = props?.items || [];
  return <div className="catalog-card status-summary">
    <div className="kpi-label">전체 {format(props?.total ?? 0)}건</div>
    {items.length ? items.map((item, i) => <div key={i} className="status-item">
      <div><span>{item.label}</span><span>{format(item.value)}건 · {format(item.share)}%</span></div>
      <progress aria-label={`${item.label} 비율`} max="100" value={item.share} />
    </div>) : <div className="widget-empty">결과 없음</div>}
  </div>;
}

export function EventTimeline({ props }) {
  const items = props?.items || [];
  return <div className="catalog-card">{items.length ? <ol className="event-timeline">
    {items.map((item, i) => <li key={i}><time dateTime={item.occurredAt}>{item.occurredAt.length === 10
      ? new Date(item.occurredAt).toLocaleDateString("ko-KR") : new Date(item.occurredAt).toLocaleString("ko-KR")}</time>
      <strong>{item.title}</strong>{item.description ? <p>{item.description}</p> : null}</li>)}
  </ol> : <div className="widget-empty">결과 없음</div>}</div>;
}

export function DetailCard({ props }) {
  const fields = props?.fields || [];
  return <div className="catalog-card">{fields.length ? <dl className="detail-fields">
    {fields.map((field, i) => <div key={i}><dt>{field.label}</dt><dd>{format(field.value)}</dd></div>)}
  </dl> : <div className="widget-empty">결과 없음</div>}</div>;
}
