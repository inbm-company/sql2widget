import json
import secrets
from typing import Any

from app.db import execute, fetch_all, fetch_one, get_conn


def _id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(8)}"


def list_conversations(tenant_id: str, user_id: str) -> list[dict]:
    return fetch_all(
        """
        SELECT id, title, created_at, updated_at
        FROM conversations
        WHERE tenant_id = %s AND user_id = %s
        ORDER BY updated_at DESC
        """,
        (tenant_id, user_id),
    )


def create_conversation(tenant_id: str, user_id: str, title: str | None = None) -> dict:
    conv_id = _id("conv")
    stage_id = _id("stg")
    final_title = title or "새 대화"
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO conversations (id, tenant_id, user_id, title)
                VALUES (%s, %s, %s, %s)
                RETURNING id, title, created_at, updated_at
                """,
                (conv_id, tenant_id, user_id, final_title),
            )
            row = cur.fetchone()
            cur.execute(
                """
                INSERT INTO stages (id, conversation_id, tenant_id, user_id)
                VALUES (%s, %s, %s, %s)
                """,
                (stage_id, conv_id, tenant_id, user_id),
            )
    return row


def get_conversation(conversation_id: str, tenant_id: str, user_id: str) -> dict | None:
    conv = fetch_one(
        """
        SELECT id, title, created_at, updated_at
        FROM conversations
        WHERE id = %s AND tenant_id = %s AND user_id = %s
        """,
        (conversation_id, tenant_id, user_id),
    )
    if not conv:
        return None
    messages = fetch_all(
        """
        SELECT id, role, content, artifact, created_at
        FROM messages
        WHERE conversation_id = %s
        ORDER BY created_at ASC
        """,
        (conversation_id,),
    )
    for m in messages:
        if m.get("artifact") and isinstance(m["artifact"], str):
            m["artifact"] = json.loads(m["artifact"])
    return {**conv, "messages": messages}


def add_message(
    conversation_id: str,
    role: str,
    content: str,
    artifact: dict[str, Any] | None = None,
) -> dict:
    msg_id = _id("msg")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO messages (id, conversation_id, role, content, artifact)
                VALUES (%s, %s, %s, %s, %s::jsonb)
                RETURNING id, role, content, artifact, created_at
                """,
                (
                    msg_id,
                    conversation_id,
                    role,
                    content,
                    json.dumps(artifact, default=str) if artifact is not None else None,
                ),
            )
            row = cur.fetchone()
            cur.execute(
                "UPDATE conversations SET updated_at = now() WHERE id = %s",
                (conversation_id,),
            )
    if row.get("artifact") and isinstance(row["artifact"], str):
        row["artifact"] = json.loads(row["artifact"])
    return row


def touch_title_from_message(conversation_id: str, message: str) -> None:
    title = message.strip().replace("\n", " ")[:40] or "새 대화"
    execute(
        """
        UPDATE conversations
        SET title = %s, updated_at = now()
        WHERE id = %s AND title = '새 대화'
        """,
        (title, conversation_id),
    )


def update_conversation(
    conversation_id: str,
    tenant_id: str,
    user_id: str,
    title: str,
) -> dict | None:
    final_title = title.strip()[:120] or "새 대화"
    return fetch_one(
        """
        UPDATE conversations
        SET title = %s, updated_at = now()
        WHERE id = %s AND tenant_id = %s AND user_id = %s
        RETURNING id, title, created_at, updated_at
        """,
        (final_title, conversation_id, tenant_id, user_id),
    )


def delete_conversation(conversation_id: str, tenant_id: str, user_id: str) -> bool:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM conversations
                WHERE id = %s AND tenant_id = %s AND user_id = %s
                """,
                (conversation_id, tenant_id, user_id),
            )
            return cur.rowcount > 0
