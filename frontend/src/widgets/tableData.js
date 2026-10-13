export function tableRows(rows, columns, { search = "", filterKey = "", filterValue = "", sortKey = "", descending = false } = {}) {
  const text = search.trim().toLocaleLowerCase();
  const valueText = (value) => String(value ?? "");
  const result = rows.filter((row) =>
    (!filterKey || filterValue === "" || valueText(row[filterKey]) === filterValue)
    && (!text || columns.some((column) => valueText(row[column.key]).toLocaleLowerCase().includes(text))));
  if (sortKey) result.sort((a, b) => {
    const x = a[sortKey], y = b[sortKey];
    const order = typeof x === "number" && typeof y === "number"
      ? x - y : valueText(x).localeCompare(valueText(y), "ko", { numeric: true });
    return descending ? -order : order;
  });
  return result;
}

export function lineChartData(series) {
  const points = new Map();
  series.forEach((entry, index) => (entry.points || []).forEach((point) => {
    const key = String(point.x);
    if (!points.has(key)) points.set(key, { x: key });
    points.get(key)[`s${index}`] = point.y;
  }));
  return [...points.values()];
}
