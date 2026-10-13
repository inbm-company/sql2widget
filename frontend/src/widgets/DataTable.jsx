import { useMemo, useState } from "react";
import { tableRows } from "./tableData.js";

export default function DataTable({ props, filterable = false }) {
  const columns = props?.columns || [];
  const rows = props?.rows || [];
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState({ key: "", descending: false });
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(10);
  const [filterKey, setFilterKey] = useState("");
  const [filterValue, setFilterValue] = useState("");
  const filtered = useMemo(() => tableRows(rows, columns, {
    search, filterKey, filterValue, sortKey: sort.key, descending: sort.descending,
  }), [rows, columns, search, filterKey, filterValue, sort]);
  const maxPage = Math.max(0, Math.ceil(filtered.length / pageSize) - 1);
  const current = Math.min(page, maxPage);
  const visible = filtered.slice(current * pageSize, (current + 1) * pageSize);
  const values = filterKey ? [...new Set(rows.map((row) => String(row[filterKey] ?? "")))] : [];
  return (
    <div className="data-table-widget" onMouseDown={(event) => {
      if (event.target.closest("button, input, select")) event.stopPropagation();
    }} onDragStart={(event) => {
      if (event.target.closest("button, input, select")) event.preventDefault();
    }}>
      <div className="table-controls">
        <input aria-label="표 검색" placeholder="검색" value={search} onChange={(event) => { setSearch(event.target.value); setPage(0); }} />
        {filterable ? <>
          <select aria-label="필터 컬럼" value={filterKey} onChange={(event) => { setFilterKey(event.target.value); setFilterValue(""); setPage(0); }}>
            <option value="">필터 컬럼</option>
            {columns.map((column) => <option key={column.key} value={column.key}>{column.label || column.key}</option>)}
          </select>
          <select aria-label="필터 값" value={filterValue} disabled={!filterKey} onChange={(event) => { setFilterValue(event.target.value); setPage(0); }}>
            <option value="">전체</option>
            {values.filter((value) => value !== "").map((value) => <option key={value} value={value}>{value}</option>)}
          </select>
        </> : null}
        <span>{filtered.length}건</span>
      </div>
      <div className="table-wrap">
        <table className="data-table">
          <thead><tr>{columns.map((column) => (
            <th key={column.key} aria-sort={sort.key !== column.key ? "none" : sort.descending ? "descending" : "ascending"}>
              <button type="button" className="table-sort" onClick={() => {
                setSort({ key: column.key, descending: sort.key === column.key && !sort.descending }); setPage(0);
              }}>{column.label || column.key}{sort.key === column.key ? (sort.descending ? " ▼" : " ▲") : ""}</button>
            </th>
          ))}</tr></thead>
          <tbody>{visible.map((row, index) => <tr key={index}>{columns.map((column) => <td key={column.key}>{String(row[column.key] ?? "")}</td>)}</tr>)}</tbody>
          {props?.totals && rows.length ? <tfoot><tr>{columns.map((column) => <td key={column.key}>{String(props.totals[column.key] ?? "")}</td>)}</tr></tfoot> : null}
        </table>
        {!visible.length ? <div className="widget-empty">결과 없음</div> : null}
      </div>
      <div className="table-pagination">
        <select aria-label="페이지당 행 수" value={pageSize} onChange={(event) => { setPageSize(Number(event.target.value)); setPage(0); }}>
          {[10, 25, 50].map((size) => <option key={size} value={size}>{size}개씩</option>)}
        </select>
        <button type="button" className="text-btn" disabled={!current} onClick={() => setPage(current - 1)}>이전</button>
        <span>{current + 1} / {maxPage + 1}</span>
        <button type="button" className="text-btn" disabled={current >= maxPage} onClick={() => setPage(current + 1)}>다음</button>
      </div>
    </div>
  );
}
