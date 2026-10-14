// Keep explanations in the chat body, including older saved MarkdownBlock cards.
export function assistantPresentation(content, artifact) {
  const explanations = [];
  const widgets = (artifact?.widgets || []).filter((widget) => {
    if (widget.component !== "MarkdownBlock") return true;
    const markdown = widget.props?.markdown;
    if (typeof markdown === "string" && markdown.trim()) {
      explanations.push(widget.title && !markdown.trimStart().startsWith("#")
        ? `### ${widget.title}\n\n${markdown}` : markdown);
    }
    return false;
  });
  return {
    content: [content, ...explanations].filter(Boolean).join("\n\n"),
    artifact: artifact ? { ...artifact, widgets } : null,
  };
}

function tableCells(line) {
  const value = line.trim().replace(/^\|/, "").replace(/(?<!\\)\|$/, "");
  return value.split(/(?<!\\)\|/).map((cell) => cell.trim().replace(/\\\|/g, "|"));
}

// A small text-only subset: paragraphs, headings, lists, fenced code and tables.
// Unsupported markup stays visible text; no HTML or URL is interpreted.
export function chatTextBlocks(content) {
  const lines = content.replace(/\r\n?/g, "\n").split("\n");
  const blocks = [];
  let paragraph = [];
  function flushParagraph() {
    if (paragraph.length) blocks.push({ type: "paragraph", text: paragraph.join("\n") });
    paragraph = [];
  }
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    const fence = line.match(/^\s*(`{3,}|~{3,})/);
    if (fence) {
      flushParagraph();
      const code = [];
      const closing = new RegExp(`^\\s*${fence[1][0]}{${fence[1].length},}\\s*$`);
      while (i + 1 < lines.length && !closing.test(lines[i + 1])) code.push(lines[++i]);
      if (i + 1 < lines.length) i += 1;
      blocks.push({ type: "code", text: code.join("\n") });
      continue;
    }
    if (line.includes("|") && i + 1 < lines.length) {
      const columns = tableCells(line);
      const divider = tableCells(lines[i + 1]);
      if (divider.length === columns.length && divider.every((cell) => /^:?-{3,}:?$/.test(cell))) {
        flushParagraph();
        const rows = [];
        i += 1;
        while (i + 1 < lines.length && lines[i + 1].includes("|")) {
          const cells = tableCells(lines[i + 1]);
          if (cells.length !== columns.length) break;
          rows.push(cells);
          i += 1;
        }
        blocks.push({ type: "table", columns, rows });
        continue;
      }
    }
    const heading = line.match(/^#{1,6}\s+(.+)$/);
    const item = line.match(/^\s*(?:[-*+]\s+|\d+[.)]\s+)(.+)$/);
    if (heading) {
      flushParagraph();
      blocks.push({ type: "heading", text: heading[1] });
    } else if (item) {
      flushParagraph();
      const ordered = /^\s*\d/.test(line);
      const previous = blocks.at(-1);
      if (previous?.type === "list" && previous.ordered === ordered) previous.items.push(item[1]);
      else blocks.push({ type: "list", ordered, items: [item[1]] });
    } else if (!line.trim()) {
      flushParagraph();
    } else paragraph.push(line);
  }
  flushParagraph();
  return blocks;
}
