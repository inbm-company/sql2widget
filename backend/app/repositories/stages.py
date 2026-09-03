import json
import secrets
from typing import Any

from app.config import ALLOWED_COMPONENTS
from app.db import fetch_all, fetch_one, get_conn


def _id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(8)}"


def _widget_row_to_dict(row: dict) -> dict:
    props = row["props"]
    if isinstance(props, str):
        props = json.loads(props)
    return {
        "id": row["id"],
        "source_widget_id": row["source_widget_id"],
        "source_artifact_id": row["source_artifact_id"],
        "component": row["component"],
        "title": row["title"],
        "props": props,
        "layout": {
            "i": row["layout_i"],
            "x": row["layout_x"],
            "y": row["layout_y"],
            "w": row["layout_w"],
            "h": row["layout_h"],
        },
    }


def get_or_create_stage(conversation_id: str, tenant_id: str, user_id: str) -> dict | None:
    conv = fetch_one(
        """
        SELECT id FROM conversations
        WHERE id = %s AND tenant_id = %s AND user_id = %s
        """,
        (conversation_id, tenant_id, user_id),
    )
    if not conv:
        return None

    stage = fetch_one(
        "SELECT id, conversation_id, updated_at FROM stages WHERE conversation_id = %s",
        (conversation_id,),
    )
    if not stage:
        stage_id = _id("stg")
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO stages (id, conversation_id, tenant_id, user_id)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id, conversation_id, updated_at
                    """,
                    (stage_id, conversation_id, tenant_id, user_id),
                )
                stage = cur.fetchone()

    widgets = fetch_all(
        """
        SELECT * FROM stage_widgets
        WHERE stage_id = %s
        ORDER BY layout_y ASC, layout_x ASC
        """,
        (stage["id"],),
    )
    return {
        "id": stage["id"],
        "conversation_id": stage["conversation_id"],
        "updated_at": stage["updated_at"],
        "widgets": [_widget_row_to_dict(w) for w in widgets],
    }


def replace_stage_widgets(stage_id: str, widgets: list[dict[str, Any]]) -> list[dict]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM stage_widgets WHERE stage_id = %s", (stage_id,))
            result = []
            for w in widgets:
                component = w["component"]
                if component not in ALLOWED_COMPONENTS:
                    raise ValueError(f"Unsupported component: {component}")
                layout = w["layout"]
                wid = w.get("id") or _id("sw")
                layout_i = layout.get("i") or wid
                cur.execute(
                    """
                    INSERT INTO stage_widgets (
                        id, stage_id, source_widget_id, source_artifact_id,
                        component, title, props,
                        layout_i, layout_x, layout_y, layout_w, layout_h
                    )
                    VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s)
                    RETURNING *
                    """,
                    (
                        wid,
                        stage_id,
                        w.get("source_widget_id"),
                        w.get("source_artifact_id"),
                        component,
                        w.get("title") or "",
                        json.dumps(w.get("props") or {}, default=str),
                        layout_i,
                        layout["x"],
                        layout["y"],
                        layout["w"],
                        layout["h"],
                    ),
                )
                result.append(_widget_row_to_dict(cur.fetchone()))
            cur.execute("UPDATE stages SET updated_at = now() WHERE id = %s", (stage_id,))
    return result


def add_widget(stage_id: str, payload: dict[str, Any]) -> dict:
    component = payload["component"]
    if component not in ALLOWED_COMPONENTS:
        raise ValueError(f"Unsupported component: {component}")
    layout = payload["layout"]
    wid = _id("sw")
    layout_i = layout.get("i") or wid
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO stage_widgets (
                    id, stage_id, source_widget_id, source_artifact_id,
                    component, title, props,
                    layout_i, layout_x, layout_y, layout_w, layout_h
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s)
                RETURNING *
                """,
                (
                    wid,
                    stage_id,
                    payload.get("source_widget_id"),
                    payload.get("source_artifact_id"),
                    component,
                    payload.get("title") or "",
                    json.dumps(payload.get("props") or {}, default=str),
                    layout_i,
                    layout.get("x", 0),
                    layout.get("y", 0),
                    layout.get("w", 4),
                    layout.get("h", 4),
                ),
            )
            row = cur.fetchone()
            cur.execute("UPDATE stages SET updated_at = now() WHERE id = %s", (stage_id,))
    return _widget_row_to_dict(row)


def patch_widget(stage_id: str, widget_id: str, patch: dict[str, Any]) -> dict | None:
    existing = fetch_one(
        "SELECT * FROM stage_widgets WHERE id = %s AND stage_id = %s",
        (widget_id, stage_id),
    )
    if not existing:
        return None

    title = patch["title"] if patch.get("title") is not None else existing["title"]
    props = patch["props"] if patch.get("props") is not None else existing["props"]
    if isinstance(props, str):
        props = json.loads(props)
    layout = patch.get("layout")
    if layout:
        lx, ly, lw, lh, li = (
            layout["x"],
            layout["y"],
            layout["w"],
            layout["h"],
            layout.get("i") or existing["layout_i"],
        )
    else:
        lx, ly, lw, lh, li = (
            existing["layout_x"],
            existing["layout_y"],
            existing["layout_w"],
            existing["layout_h"],
            existing["layout_i"],
        )

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE stage_widgets
                SET title = %s,
                    props = %s::jsonb,
                    layout_i = %s,
                    layout_x = %s,
                    layout_y = %s,
                    layout_w = %s,
                    layout_h = %s,
                    updated_at = now()
                WHERE id = %s AND stage_id = %s
                RETURNING *
                """,
                (title, json.dumps(props, default=str), li, lx, ly, lw, lh, widget_id, stage_id),
            )
            row = cur.fetchone()
            cur.execute("UPDATE stages SET updated_at = now() WHERE id = %s", (stage_id,))
    return _widget_row_to_dict(row) if row else None


def delete_widget(stage_id: str, widget_id: str) -> bool:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM stage_widgets WHERE id = %s AND stage_id = %s",
                (widget_id, stage_id),
            )
            deleted = cur.rowcount > 0
            if deleted:
                cur.execute("UPDATE stages SET updated_at = now() WHERE id = %s", (stage_id,))
    return deleted
