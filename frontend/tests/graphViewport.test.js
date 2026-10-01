import assert from "node:assert/strict";
import test from "node:test";
import { zoomGraph, MAX_GRAPH_ZOOM, MIN_GRAPH_ZOOM } from "../src/graphViewport.js";

test("zoom keeps the graph point under the cursor stationary after panning", () => {
  const current = { zoom: 2, pan: { x: 60, y: -35 } };
  const center = { x: 700, y: 500 }, point = { x: 240, y: 380 };
  const next = zoomGraph(current, 8, point, center);
  for (const axis of ["x", "y"]) {
    const world = (point[axis] - center[axis] - current.pan[axis]) / current.zoom;
    const screen = center[axis] + next.pan[axis] + world * next.zoom;
    assert(Math.abs(screen - point[axis]) < 1e-9);
  }
});

test("zoom supports more than 400 percent and bounds extreme wheel input", () => {
  const current = { zoom: 4, pan: { x: 0, y: 0 } }, center = { x: 0, y: 0 };
  assert(zoomGraph(current, 4 * 1.3, center, center).zoom > 4);
  assert.equal(zoomGraph(current, 100000, center, center).zoom, MAX_GRAPH_ZOOM);
  assert.equal(zoomGraph(current, 0.00001, center, center).zoom, MIN_GRAPH_ZOOM);
});
