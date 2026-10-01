// Deterministic layout with reserved space for node titles. No animation loop.
export function layoutGraph(nodes, links) {
  const width = Math.max(720, Math.sqrt(nodes.length) * 230);
  const height = Math.max(480, width * 0.7);
  const points = [...nodes].sort((a, b) => a.id.localeCompare(b.id)).map((node, i) => {
    const angle = i * 2.399963;
    const radius = Math.sqrt((i + 0.5) / Math.max(nodes.length, 1)) * Math.min(width, height) * 0.4;
    return { ...node, x: width / 2 + Math.cos(angle) * radius, y: height / 2 + Math.sin(angle) * radius };
  });
  const index = new Map(points.map((node, i) => [node.id, i]));
  const edges = links.filter((link) => link.source !== link.target && index.has(link.source) && index.has(link.target));
  const degree = new Map(points.map((node) => [node.id, 0]));
  edges.forEach((edge) => {
    degree.set(edge.source, degree.get(edge.source) + 1);
    degree.set(edge.target, degree.get(edge.target) + 1);
  });
  for (let iteration = 0; iteration < 100; iteration++) {
    const force = points.map((p) => ({ x: (width / 2 - p.x) * 0.003, y: (height / 2 - p.y) * 0.003 }));
    for (let i = 0; i < points.length; i++) {
      for (let j = i + 1; j < points.length; j++) {
        const dx = points[i].x - points[j].x;
        const dy = points[i].y - points[j].y;
        const distance = Math.max(1, Math.hypot(dx, dy));
        const strength = 12000 / (distance * distance);
        force[i].x += dx / distance * strength;
        force[i].y += dy / distance * strength;
        force[j].x -= dx / distance * strength;
        force[j].y -= dy / distance * strength;
      }
    }
    for (const edge of edges) {
      const a = index.get(edge.source), b = index.get(edge.target);
      const dx = points[b].x - points[a].x, dy = points[b].y - points[a].y;
      const distance = Math.max(1, Math.hypot(dx, dy));
      const strength = (distance - 180) * 0.045 / Math.max(degree.get(edge.source), degree.get(edge.target), 1);
      force[a].x += dx / distance * strength;
      force[a].y += dy / distance * strength;
      force[b].x -= dx / distance * strength;
      force[b].y -= dy / distance * strength;
    }
    const step = 5 * (1 - iteration / 100) + 0.5;
    points.forEach((point, i) => {
      point.x = Math.max(60, Math.min(width - 60, point.x + Math.max(-step, Math.min(step, force[i].x))));
      point.y = Math.max(50, Math.min(height - 50, point.y + Math.max(-step, Math.min(step, force[i].y))));
    });
  }
  // Pack into the nearby free title-sized slot. This guarantees separation even
  // for hubs and dense graphs where link forces would otherwise pile nodes up.
  const occupied = new Set();
  const cellWidth = 260, cellHeight = 88;
  points.forEach((point) => {
    const column = Math.round(point.x / cellWidth), row = Math.round(point.y / cellHeight);
    let found = false;
    for (let radius = 0; !found; radius++) {
      const candidates = [];
      for (let dx = -radius; dx <= radius; dx++) {
        for (let dy = -radius; dy <= radius; dy++) {
          if (Math.max(Math.abs(dx), Math.abs(dy)) !== radius) continue;
          const x = (column + dx) * cellWidth, y = (row + dy) * cellHeight;
          candidates.push({ x, y, key: `${column + dx}:${row + dy}`,
            distance: Math.hypot(x - point.x, y - point.y) });
        }
      }
      candidates.sort((a, b) => a.distance - b.distance);
      const slot = candidates.find((candidate) => !occupied.has(candidate.key));
      if (slot) {
        occupied.add(slot.key);
        point.x = slot.x;
        point.y = slot.y;
        found = true;
      }
    }
  });
  const left = Math.min(0, ...points.map((point) => point.x)) - 140;
  const top = Math.min(0, ...points.map((point) => point.y)) - 50;
  points.forEach((point) => { point.x -= left; point.y -= top; });
  return { nodes: points,
    width: Math.max(720, ...points.map((point) => point.x + 140)),
    height: Math.max(480, ...points.map((point) => point.y + 60)) };

}

export function filterGraph(graph, query) {
  const search = query.trim().toLocaleLowerCase();
  const nodes = graph.nodes.filter((node) => !search || `${node.title} ${node.path}`.toLocaleLowerCase().includes(search));
  const ids = new Set(nodes.map((node) => node.id));
  return { nodes, links: graph.links.filter((edge) => ids.has(edge.source) && ids.has(edge.target)) };
}
