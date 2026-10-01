import secrets
from contextlib import contextmanager

import psycopg
from pgvector import Vector
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row

from app.config import CHAT_VECTOR_DATABASE_URL


def _id() -> str:
    return f"me_{secrets.token_hex(8)}"


@contextmanager
def get_conn():
    conn = psycopg.connect(CHAT_VECTOR_DATABASE_URL, row_factory=dict_row)
    register_vector(conn)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def upsert_embedding(
    *,
    tenant_id: str,
    conversation_id: str,
    message_id: str,
    role: str,
    content: str,
    embedding: list[float],
) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO message_embeddings
                    (id, tenant_id, conversation_id, message_id, role, content, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (message_id) DO UPDATE SET
                    content = EXCLUDED.content,
                    embedding = EXCLUDED.embedding
                """,
                (_id(), tenant_id, conversation_id, message_id, role, content, Vector(embedding)),
            )


def search_similar(
    tenant_id: str,
    embedding: list[float],
    *,
    limit: int = 5,
) -> list[dict]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    message_id,
                    conversation_id,
                    role,
                    content,
                    1 - (embedding <=> %s) AS similarity
                FROM message_embeddings
                WHERE tenant_id = %s
                ORDER BY embedding <=> %s
                LIMIT %s
                """,
                (Vector(embedding), tenant_id, Vector(embedding), limit),
            )
            return cur.fetchall()


def delete_conversation_embeddings(tenant_id: str, conversation_ids: list[str]) -> None:
    if not conversation_ids:
        return
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM message_embeddings WHERE tenant_id = %s AND conversation_id = ANY(%s)",
                (tenant_id, conversation_ids),
            )
