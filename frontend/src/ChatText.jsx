import { chatTextBlocks } from "./chatText.js";

function inlineText(text) {
  return text.split(/(`[^`\n]+`|\*\*[^*\n]+\*\*)/g).map((part, index) => {
    if (part.startsWith("`") && part.endsWith("`")) return <code key={index}>{part.slice(1, -1)}</code>;
    if (part.startsWith("**") && part.endsWith("**")) return <strong key={index}>{part.slice(2, -2)}</strong>;
    return part;
  });
}

export default function ChatText({ content }) {
  return <div className="msg-content chat-text">
    {chatTextBlocks(content).map((block, index) => {
      if (block.type === "heading") return <h3 key={index}>{inlineText(block.text)}</h3>;
      if (block.type === "code") return <pre key={index}><code>{block.text}</code></pre>;
      if (block.type === "list") {
        const List = block.ordered ? "ol" : "ul";
        return <List key={index}>{block.items.map((item, row) => <li key={row}>{inlineText(item)}</li>)}</List>;
      }
      if (block.type === "table") return <div className="chat-text-table" key={index} tabIndex={0} role="region" aria-label="답변 표">
        <table>
          <thead><tr>{block.columns.map((cell, column) => <th key={column} scope="col">{inlineText(cell)}</th>)}</tr></thead>
          <tbody>{block.rows.map((row, rowIndex) => <tr key={rowIndex}>
            {row.map((cell, column) => <td key={column}>{inlineText(cell)}</td>)}
          </tr>)}</tbody>
        </table>
      </div>;
      return <p key={index}>{inlineText(block.text)}</p>;
    })}
  </div>;
}
