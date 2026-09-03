#!/usr/bin/env python3
"""Apply customer demo DB SQL migrations (SOC schema)."""

from pathlib import Path

import psycopg

from app.config import DEMO_CUSTOMER_DATABASE_URL

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "sql" / "sample_customer"


def main() -> None:
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    with psycopg.connect(DEMO_CUSTOMER_DATABASE_URL) as conn:
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
                    print(f"skip customer {version}")
                    continue
                sql = path.read_text(encoding="utf-8")
                cur.execute(sql)
                cur.execute(
                    "INSERT INTO schema_migrations (version) VALUES (%s) ON CONFLICT DO NOTHING",
                    (version,),
                )
                print(f"applied customer {version}")
        conn.commit()
    print("customer migrations done")


if __name__ == "__main__":
    main()
