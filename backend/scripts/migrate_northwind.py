#!/usr/bin/env python3
"""Apply the local Northwind-style fixture schema."""

from pathlib import Path

import psycopg

from app.config import NORTHWIND_DATABASE_URL


MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "sql" / "northwind"


def main() -> None:
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    with psycopg.connect(NORTHWIND_DATABASE_URL) as conn:
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
                    print(f"skip northwind {version}")
                    continue
                cur.execute(path.read_text(encoding="utf-8"))
                cur.execute(
                    "INSERT INTO schema_migrations (version) VALUES (%s)", (version,)
                )
                print(f"applied northwind {version}")
        conn.commit()
    print("northwind migrations done")


if __name__ == "__main__":
    main()
