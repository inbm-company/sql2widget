export const MIN_GRAPH_ZOOM = 0.1;
export const MAX_GRAPH_ZOOM = 32;

export function zoomGraph(viewport, requestedZoom, point, center) {
  const zoom = Math.max(MIN_GRAPH_ZOOM, Math.min(MAX_GRAPH_ZOOM, requestedZoom));
  const ratio = zoom / viewport.zoom;
  return { zoom, pan: {
    x: point.x - center.x - (point.x - center.x - viewport.pan.x) * ratio,
    y: point.y - center.y - (point.y - center.y - viewport.pan.y) * ratio,
  } };
}
