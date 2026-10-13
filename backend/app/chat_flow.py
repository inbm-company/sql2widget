"""Build follow-up context from this conversation's current database turns."""

from typing import Any

MAX_MESSAGES = 20


def conversation_flow(
    messages: list[dict[str, Any]] | None, connection_id: str | None,
) -> dict[str, Any]:
    """Keep answered turns; stop at another DB or legacy history with no DB identity.

    Widget SQL and Markdown explain what an earlier answer meant. Result rows,
    credentials and diagnostic metadata are not copied into model context.
    """
    history = []
    last_route = None
    waiting_for_user = False
    for message in reversed((messages or [])[-MAX_MESSAGES:]):
        role = message.get("role")
        if role == "assistant":
            meta = message.get("meta") or {}
            if "connection_id" not in meta or meta["connection_id"] != connection_id:
                break
            if last_route is None:
                last_route = meta.get("route")
            entry = {"role": role, "content": message.get("content") or ""}
            widgets = []
            for widget in (message.get("artifact") or {}).get("widgets") or []:
                reference = {key: widget[key] for key in ("component", "title", "sql") if widget.get(key)}
                markdown = (widget.get("props") or {}).get("markdown")
                mapping = (widget.get("props") or {}).get("column_map")
                if isinstance(mapping, dict):
                    reference["column_map"] = mapping
                if markdown:
                    reference["markdown"] = markdown
                if reference:
                    widgets.append(reference)
            if widgets:
                entry["widgets"] = widgets
            history.append(entry)
            waiting_for_user = True
        elif role == "user" and waiting_for_user:
            history.append({"role": role, "content": message.get("content") or ""})
            waiting_for_user = False
    return {"last_route": last_route, "history": list(reversed(history))}
