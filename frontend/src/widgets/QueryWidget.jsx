import { api } from "../api";
import { useSWR } from "../store";
import WidgetRenderer from "./WidgetRenderer.jsx";
import { widgetDataUrl } from "./widgetData.js";

export default function QueryWidget({ widget, projectId, conversationId, compact = false }) {
  const url = widgetDataUrl(widget, { projectId, conversationId });
  const { data, error, isLoading, isValidating, mutate } = useSWR(
    url ? [url, widget.component, widget.title, widget.query_ref?.connection_id, widget.query_ref?.sql || widget.sql, widget.props] : null,
    () => api.getWidgetData(url),
    { revalidateOnFocus: false, revalidateOnMount: true, shouldRetryOnError: false }
  );
  if (!url) return <WidgetRenderer component={widget.component} props={widget.props} compact={compact} />;

  return (
    <div className="query-widget">
      <div className="widget-data-actions">
        <button
          type="button"
          className="text-btn"
          disabled={isValidating}
          aria-label={`${widget.title || widget.component} 데이터 새로고침`}
          onMouseDown={(event) => event.stopPropagation()}
          onDragStart={(event) => event.preventDefault()}
          onClick={(event) => { event.stopPropagation(); mutate(); }}
        >
          {isValidating ? "조회 중…" : error ? "다시 조회" : "새로고침"}
        </button>
      </div>
      {error ? (
        <div className="widget-data-status" role="alert">{error.message}</div>
      ) : isLoading || !data ? (
        <div className="widget-data-status" role="status">데이터를 불러오는 중…</div>
      ) : (
        <WidgetRenderer component={widget.component} props={data.props} compact={compact} />
      )}
    </div>
  );
}
