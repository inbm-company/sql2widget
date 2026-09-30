import assert from "node:assert/strict";
import test from "node:test";
import { filterGraph, layoutGraph } from "../src/graphLayout.js";

const nodes = [{ id: "a", title: "첫 문서", path: "a.md" }, { id: "b", title: "두 번째", path: "folder/B.md" }, { id: "c", title: "독립", path: "c.md" }];
const links = [{ source: "a", target: "b" }];

test("search keeps only edges whose documents remain visible", () => {
  assert.deepEqual(filterGraph({ nodes, links }, " FOLDER/b "), { nodes: [nodes[1]], links: [] });
  assert.deepEqual(filterGraph({ nodes, links }, "없는 문서"), { nodes: [], links: [] });
  assert.deepEqual(filterGraph({ nodes, links }, ""), { nodes, links });
});

test("layout remains finite and bounded for isolated nodes, loops and capped graphs", () => {
  for (const input of [[], nodes.slice(0, 1), nodes, Array.from({ length: 500 }, (_, i) => ({ id: String(i) }))]) {
    const graph = layoutGraph(input, [...links, { source: "a", target: "a" }, { source: "a", target: "missing" }]);
    assert.equal(graph.nodes.length, input.length);
    for (const point of graph.nodes) {
      assert(Number.isFinite(point.x) && Number.isFinite(point.y));
      assert(point.x >= 0 && point.x <= graph.width && point.y >= 0 && point.y <= graph.height);
    }
  }
  assert.deepEqual(layoutGraph(nodes, links), layoutGraph([...nodes].reverse(), links));
});
