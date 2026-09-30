#!/usr/bin/env python3
"""Apply chat vector DB SQL migrations (pgvector, message embeddings, command catalog)."""

from pathlib import Path

import psycopg

from app.config import CHAT_EMBEDDING_DIM, CHAT_VECTOR_DATABASE_URL

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "sql" / "chat_vector"


def main() -> None:
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    with psycopg.connect(CHAT_VECTOR_DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            for path in files:
                version = path.name
                cur.execute(
                    "SELECT 1 FROM schema_migrations WHERE version = %s", (version,)
                )
                if cur.fetchone():
                    print(f"skip chat_vector {version}")
                    continue
                sql = path.read_text(encoding="utf-8").replace(
                    "__EMBEDDING_DIM__", str(CHAT_EMBEDDING_DIM)
                )
                cur.execute(sql)
                cur.execute(
                    "INSERT INTO schema_migrations (version) VALUES (%s) ON CONFLICT DO NOTHING",
                    (version,),
                )
                print(f"applied chat_vector {version} (dim={CHAT_EMBEDDING_DIM})")
        conn.commit()
    print("chat_vector migrations done")


if __name__ == "__main__":
    main()
