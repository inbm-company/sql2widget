"""DB-scoped expected-question retrieval, separate from chat history."""

import hashlib
import secrets

from pgvector import Vector
from psycopg.types.json import Jsonb

from app.repositories.message_embeddings import get_conn


def upsert_questions(*, tenant_id, connection_id, schema_hash, database_info, entries):
    """Persist a validated batch atomically; repeated questions update in place."""
    saved = []
    with get_conn() as conn:
        with conn.cursor() as cur:
            for entry in entries:
                normalized = " ".join(entry["question"].split()).casefold()
                question_key = hashlib.sha256(normalized.encode()).hexdigest()
                cur.execute(
                    """
                    INSERT INTO question_catalog
                        (id, tenant_id, connection_id, question, question_key,
                         database_info, schema_hash, plan, embedding_model, embedding)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (tenant_id, connection_id, schema_hash,
                                 embedding_model, question_key)
                    DO UPDATE SET question = EXCLUDED.question,
                        database_info = EXCLUDED.database_info, plan = EXCLUDED.plan,
                        embedding = EXCLUDED.embedding, updated_at = now()
                    RETURNING id, question, database_info, plan, embedding_model
                    """,
                    (f"qst_{secrets.token_hex(8)}", tenant_id, connection_id,
                     entry["question"], question_key, Jsonb(database_info), schema_hash,
                     Jsonb(entry["plan"]), entry["embedding_model"], Vector(entry["embedding"])),
                )
                saved.append(cur.fetchone())
    return saved


def list_questions(*, tenant_id, connection_id, limit=200, offset=0):
    """Return previously saved questions for the admin screen, newest first."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS total FROM question_catalog "
                "WHERE tenant_id = %s AND connection_id = %s",
                (tenant_id, connection_id),
            )
            total = cur.fetchone()["total"]
            cur.execute(
                """
                SELECT id, question, plan, database_info, embedding_model, created_at
                FROM question_catalog
                WHERE tenant_id = %s AND connection_id = %s
                ORDER BY created_at DESC, id
                LIMIT %s OFFSET %s
                """,
                (tenant_id, connection_id, limit, offset),
            )
            return total, cur.fetchall()


def search_questions(*, tenant_id, connection_id, schema_hash, embedding_model,
                     embedding, limit=5, min_similarity=0.75, offset=0):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, question, connection_id, database_info, plan,
                       embedding_model, 1 - (embedding <=> %s) AS similarity
                FROM question_catalog
                WHERE tenant_id = %s AND connection_id = %s
                  AND schema_hash = %s AND embedding_model = %s
                  AND 1 - (embedding <=> %s) >= %s
                ORDER BY embedding <=> %s, id
                LIMIT %s OFFSET %s
                """,
                (Vector(embedding), tenant_id, connection_id, schema_hash,
                 embedding_model, Vector(embedding), min_similarity, Vector(embedding), limit, offset),
            )
            return cur.fetchall()
