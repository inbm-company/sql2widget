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

test("dense graphs and high-degree hubs reserve separate node and title spaces", () => {
  for (const size of [200, 500]) {
    const input = Array.from({ length: size }, (_, i) => ({ id: `node-${i}`, title: "긴 문서 제목을 표시하는 노드입니다", path: `${i}.md` }));
    const denseLinks = input.slice(1).flatMap((node, i) => [
      { source: input[0].id, target: node.id },
      { source: node.id, target: input[(i + 2) % size].id },
    ]);
    const graph = layoutGraph(input, denseLinks);
    for (let i = 0; i < graph.nodes.length; i++) {
      for (let j = i + 1; j < graph.nodes.length; j++) {
        const a = graph.nodes[i], b = graph.nodes[j];
        assert(Math.abs(a.x - b.x) >= 260 || Math.abs(a.y - b.y) >= 88,
          `Nodes ${a.id} and ${b.id} must reserve distinct title slots`);
      }
    }
    assert.deepEqual(graph, layoutGraph([...input].reverse(), denseLinks));
  }
});
