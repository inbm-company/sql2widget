import json
import secrets
from typing import Any

from app.db import execute, fetch_all, fetch_one, get_conn
from app.chat_turns import message_turns
from app.widget_queries import widget_definition
from app.repositories import message_embeddings


def _id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(8)}"


def list_conversations(tenant_id: str, user_id: str, project_id: str) -> list[dict]:
    return fetch_all(
        """
        SELECT id, title, created_at, updated_at
        FROM conversations
        WHERE tenant_id = %s AND user_id = %s AND project_id = %s
        ORDER BY updated_at DESC
        """,
        (tenant_id, user_id, project_id),
    )


def create_conversation(
    tenant_id: str, user_id: str, project_id: str, title: str | None = None
) -> dict | None:
    conv_id = _id("conv")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id FROM projects
                WHERE id = %s AND tenant_id = %s AND user_id = %s
                FOR UPDATE
                """,
                (project_id, tenant_id, user_id),
            )
            if not cur.fetchone():
                return None

            requested_title = (title or "").strip()
            if not requested_title or requested_title == "New Chat":
                cur.execute(
                    """
                    SELECT COUNT(*)::int AS count
                    FROM conversations
                    WHERE project_id = %s
                    """,
                    (project_id,),
                )
                final_title = f"New Chat {cur.fetchone()['count'] + 1}"
            else:
                final_title = requested_title[:120]

            cur.execute(
                """
                INSERT INTO conversations (id, tenant_id, user_id, project_id, title)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, title, created_at, updated_at
                """,
                (conv_id, tenant_id, user_id, project_id, final_title),
            )
            row = cur.fetchone()
            if row:
                cur.execute(
                    "UPDATE projects SET updated_at = now() WHERE id = %s",
                    (project_id,),
                )
    return row


def get_conversation(conversation_id: str, tenant_id: str, user_id: str) -> dict | None:
    conv = fetch_one(
        """
        SELECT id, project_id, title, created_at, updated_at
        FROM conversations
        WHERE id = %s AND tenant_id = %s AND user_id = %s
        """,
        (conversation_id, tenant_id, user_id),
    )
    if not conv:
        return None
    messages = fetch_all(
        """
        SELECT id, role, content, artifact, meta, created_at
        FROM messages
        WHERE conversation_id = %s
        ORDER BY created_at ASC
        """,
        (conversation_id,),
    )
    for m in messages:
        if m.get("artifact") and isinstance(m["artifact"], str):
            m["artifact"] = json.loads(m["artifact"])
        if isinstance(m.get("meta"), str):
            m["meta"] = json.loads(m["meta"])
        if m.get("artifact"):
            m["artifact"] = {**m["artifact"], "widgets": [
                widget_definition(widget, (m.get("meta") or {}).get("connection_id"))
                for widget in m["artifact"].get("widgets") or []
            ]}
    return {**conv, "messages": messages}


def find_source_widget(project_id, artifact_id, widget_id, tenant_id, user_id):
    """Recover a legacy Stage widget's DB from its owned source message."""
    if not artifact_id or not widget_id:
        return None
    message = fetch_one(
        """SELECT m.artifact, m.meta FROM messages m
        JOIN conversations c ON c.id = m.conversation_id
        WHERE c.project_id = %s AND c.tenant_id = %s AND c.user_id = %s
          AND m.role = 'assistant' AND m.artifact->>'artifact_id' = %s""",
        (project_id, tenant_id, user_id, artifact_id),
    )
    if not message:
        return None
    artifact, meta = message["artifact"], message.get("meta") or {}
    if isinstance(artifact, str):
        artifact = json.loads(artifact)
    if isinstance(meta, str):
        meta = json.loads(meta)
    for widget in artifact.get("widgets") or []:
        if widget.get("widget_id") == widget_id:
            return widget_definition(widget, meta.get("connection_id"))
    return None


def add_message(
    conversation_id: str,
    role: str,
    content: str,
    artifact: dict[str, Any] | None = None,
    meta: dict[str, Any] | None = None,
) -> dict:
    msg_id = _id("msg")
    with get_conn() as conn:
        with conn.cursor() as cur:
            parent = (meta or {}).get("reply_to_message_id")
            if role == "assistant" and parent:
                cur.execute("SELECT id, meta FROM messages WHERE id = %s AND conversation_id = %s AND role = 'user' FOR UPDATE",
                            (parent, conversation_id))
                source = cur.fetchone()
                if not source:
                    raise MessageDeletedError("원래 질문이 삭제되어 답변을 저장하지 않았습니다.")
                source_meta = source.get("meta") or {}
                if isinstance(source_meta, str):
                    source_meta = json.loads(source_meta)
                attempt = (meta or {}).get("response_request_id")
                if attempt and source_meta.get("active_response_id") != attempt:
                    raise MessageDeletedError("더 최근에 시작한 응답이 있어 이전 응답을 저장하지 않았습니다.")
            cur.execute(
                """
                INSERT INTO messages (id, conversation_id, role, content, artifact, meta)
                VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb)
                RETURNING id, role, content, artifact, meta, created_at
                """,
                (
                    msg_id,
                    conversation_id,
                    role,
                    content,
                    json.dumps(artifact, default=str) if artifact is not None else None,
                    json.dumps(meta, default=str) if meta is not None else None,
                ),
            )
            row = cur.fetchone()
            if role == "assistant" and parent and (meta or {}).get("response_request_id"):
                cur.execute("UPDATE messages SET meta = COALESCE(meta, '{}'::jsonb) || '{\"response_pending\":false}'::jsonb WHERE id = %s",
                            (parent,))
            cur.execute(
                "UPDATE conversations SET updated_at = now() WHERE id = %s",
                (conversation_id,),
            )
            cur.execute(
                """
                UPDATE projects
                SET updated_at = now()
                WHERE id = (SELECT project_id FROM conversations WHERE id = %s)
                """,
                (conversation_id,),
            )
    if row.get("artifact") and isinstance(row["artifact"], str):
        row["artifact"] = json.loads(row["artifact"])
    if isinstance(row.get("meta"), str):
        row["meta"] = json.loads(row["meta"])
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


class MessageDeletedError(Exception):
    pass


def delete_message(conversation_id: str, message_id: str, tenant_id: str, user_id: str) -> bool:
    """Delete exactly one owned message, preserving all other questions and replies."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT m.id, m.role, m.meta, m.artifact FROM messages m
                JOIN conversations c ON c.id = m.conversation_id
                WHERE m.id = %s AND m.conversation_id = %s
                  AND c.tenant_id = %s AND c.user_id = %s FOR UPDATE OF m""",
                (message_id, conversation_id, tenant_id, user_id))
            selected = cur.fetchone()
            if not selected:
                return False
            if isinstance(selected.get("meta"), str):
                selected["meta"] = json.loads(selected["meta"])
            if selected["role"] == "user":
                # Freeze legacy associations before removing the question. Its retained
                # answers must not become answers to an unrelated preceding question.
                cur.execute("SELECT id, role, content, meta FROM messages WHERE conversation_id = %s ORDER BY created_at ASC",
                            (conversation_id,))
                messages = cur.fetchall()
                for message in messages:
                    if isinstance(message.get("meta"), str):
                        message["meta"] = json.loads(message["meta"])
                turn = next(turn for turn in message_turns(messages)
                            if (turn["question"] or {}).get("id") == message_id)
                for answer in turn["answers"]:
                    if not (answer.get("meta") or {}).get("reply_to_message_id"):
                        cur.execute("UPDATE messages SET meta = COALESCE(meta, '{}'::jsonb) || %s::jsonb WHERE id = %s AND conversation_id = %s",
                                    (json.dumps({"reply_to_message_id": message_id}), answer["id"], conversation_id))
            if selected["role"] == "assistant":
                # Older pinned widgets can rely on the source answer for their DB.
                # Copy its reference only; preserve Stage layout and display settings.
                artifact = selected.get("artifact") or {}
                if isinstance(artifact, str):
                    artifact = json.loads(artifact)
                for widget in artifact.get("widgets") or []:
                    definition = widget_definition(widget, (selected.get("meta") or {}).get("connection_id"))
                    reference = definition.get("query_ref") or {}
                    if reference.get("sql") and reference.get("connection_id"):
                        cur.execute(
                            """UPDATE stage_widgets sw SET props = jsonb_set(sw.props, '{__query_ref}', %s::jsonb)
                            FROM stages st, conversations c WHERE sw.stage_id = st.id AND st.project_id = c.project_id
                              AND c.id = %s AND c.tenant_id = %s AND c.user_id = %s
                              AND sw.source_artifact_id = %s AND sw.source_widget_id = %s
                              AND sw.props->'__query_ref'->>'connection_id' IS NULL""",
                            (json.dumps(reference), conversation_id, tenant_id, user_id,
                             artifact.get("artifact_id"), widget.get("widget_id")))
            cur.execute("DELETE FROM messages WHERE conversation_id = %s AND id = %s", (conversation_id, message_id))
            message_embeddings.delete_message_embeddings(tenant_id, [message_id])
            cur.execute("UPDATE conversations SET updated_at = now() WHERE id = %s", (conversation_id,))
            cur.execute("UPDATE projects SET updated_at = now() WHERE id = (SELECT project_id FROM conversations WHERE id = %s)",
                        (conversation_id,))
            return True


def with_message_lock(conversation_id, message_id, work):
    """Do not recreate a vector copy after a concurrent message deletion."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM messages WHERE id = %s AND conversation_id = %s FOR UPDATE",
                        (message_id, conversation_id))
            if not cur.fetchone():
                raise MessageDeletedError("메시지가 삭제되어 작업을 중지했습니다.")
            work()


def mark_response_pending(conversation_id, question_id, request_id, mode):
    row = fetch_one(
        """UPDATE messages SET meta = COALESCE(meta, '{}'::jsonb) || %s::jsonb
        WHERE id = %s AND conversation_id = %s AND role = 'user' RETURNING id""",
        (json.dumps({"response_pending": True, "active_response_id": request_id, "pending_response_mode": mode}),
         question_id, conversation_id))
    return row is not None
