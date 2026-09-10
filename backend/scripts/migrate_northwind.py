#!/usr/bin/env python3
"""Apply the local full Northwind fixture and normalize its reporting dates."""

import base64
import gzip
from pathlib import Path

import psycopg

from app.config import NORTHWIND_DATABASE_URL


MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "sql" / "northwind"
FULL_DATASET_PATH = MIGRATIONS_DIR / "northwind_full.sql.gz.b64"
FULL_DATASET_MIGRATION = "003_full_northwind_recent.sql"

RECENT_DATE_SQL = """
WITH date_bounds AS (
    SELECT
        MIN(event_date) AS min_date,
        MAX(event_date) AS max_date
    FROM (
        SELECT order_date AS event_date FROM orders
        UNION ALL SELECT required_date FROM orders
        UNION ALL SELECT shipped_date FROM orders WHERE shipped_date IS NOT NULL
    ) AS all_dates
)
UPDATE orders
SET
    order_date = DATE '2026-08-01'
        + ROUND(
            ((orders.order_date - date_bounds.min_date)::numeric
                / NULLIF((date_bounds.max_date - date_bounds.min_date)::numeric, 0))
            * 40
        )::integer,
    required_date = DATE '2026-08-01'
        + ROUND(
            ((orders.required_date - date_bounds.min_date)::numeric
                / NULLIF((date_bounds.max_date - date_bounds.min_date)::numeric, 0))
            * 40
        )::integer,
    shipped_date = CASE
        WHEN orders.shipped_date IS NULL THEN NULL
        ELSE DATE '2026-08-01'
            + ROUND(
                ((orders.shipped_date - date_bounds.min_date)::numeric
                    / NULLIF((date_bounds.max_date - date_bounds.min_date)::numeric, 0))
                * 40
            )::integer
    END
FROM date_bounds;
"""


def full_dataset_sql() -> str:
    """Load the vendored, compressed canonical PostgreSQL Northwind dump."""
    encoded = FULL_DATASET_PATH.read_bytes()
    return gzip.decompress(base64.b64decode(encoded)).decode("utf-8")


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
                if version == FULL_DATASET_MIGRATION:
                    cur.execute(full_dataset_sql())
                    cur.execute(RECENT_DATE_SQL)
                else:
                    cur.execute(path.read_text(encoding="utf-8"))
                cur.execute(
                    "INSERT INTO schema_migrations (version) VALUES (%s)", (version,)
                )
                print(f"applied northwind {version}")
        conn.commit()
    print("northwind migrations done")


if __name__ == "__main__":
    main()
