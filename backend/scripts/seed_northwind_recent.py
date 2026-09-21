#!/usr/bin/env python3
"""Create a deterministic, Northwind-native recent operational data delta."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from random import Random


SEED_VERSION = "northwind_recent_operational_v1"
ORDER_COUNT = 3_000
DETAIL_COUNT = 0
START_DATE = date(2026, 8, 1)
END_DATE = date(2026, 9, 11)


def _operational_date(rng: Random) -> date:
    """Bias activity toward the present without concentrating every row on one day."""
    if rng.random() < 0.08:
        return END_DATE
    span = (END_DATE - START_DATE).days
    return START_DATE + timedelta(days=int(rng.triangular(0, span, span * 0.72)))


def seed(cur) -> tuple[int, int]:
    """Insert recent orders and details once; return inserted row totals."""
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS northwind_data_provenance (
            seed_version TEXT PRIMARY KEY,
            source_type TEXT NOT NULL,
            description TEXT NOT NULL,
            generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            order_count INTEGER NOT NULL,
            order_detail_count INTEGER NOT NULL,
            period_start DATE NOT NULL,
            period_end DATE NOT NULL
        )
        """
    )
    cur.execute(
        "SELECT 1 FROM northwind_data_provenance WHERE seed_version = %s",
        (SEED_VERSION,),
    )
    if cur.fetchone():
        print(f"skip Northwind operational seed {SEED_VERSION}")
        return 0, 0

    cur.execute(
        """
        SELECT customer_id, company_name, address, city, region, postal_code, country
        FROM customers ORDER BY customer_id
        """
    )
    customers = cur.fetchall()
    cur.execute("SELECT employee_id FROM employees ORDER BY employee_id")
    employee_ids = [row[0] for row in cur.fetchall()]
    cur.execute("SELECT shipper_id FROM shippers ORDER BY shipper_id")
    shipper_ids = [row[0] for row in cur.fetchall()]
    cur.execute("SELECT product_id, unit_price FROM products ORDER BY product_id")
    products = cur.fetchall()
    if not all((customers, employee_ids, shipper_ids, products)):
        raise RuntimeError("Canonical Northwind reference data is incomplete")

    cur.execute("SELECT COALESCE(MAX(order_id), 0) FROM orders")
    next_order_id = cur.fetchone()[0] + 1
    rng = Random(20260911)
    order_rows = []
    detail_rows = []

    for index in range(ORDER_COUNT):
        order_id = next_order_id + index
        customer = customers[rng.randrange(len(customers))]
        order_date = _operational_date(rng)
        required_date = min(order_date + timedelta(days=rng.randint(1, 3)), END_DATE)
        is_open = order_date >= END_DATE - timedelta(days=2) and rng.random() < 0.72
        shipped_date = None if is_open else min(
            order_date + timedelta(days=rng.randint(0, 2)), END_DATE
        )
        order_rows.append(
            (
                order_id,
                customer[0],
                rng.choice(employee_ids),
                order_date,
                required_date,
                shipped_date,
                rng.choice(shipper_ids),
                Decimal(str(round(rng.uniform(4.5, 85.0), 2))),
                customer[1],
                customer[2],
                customer[3],
                customer[4],
                customer[5],
                customer[6],
            )
        )
        for product_id, unit_price in rng.sample(products, rng.randint(1, 5)):
            detail_rows.append(
                (
                    order_id,
                    product_id,
                    unit_price,
                    rng.randint(1, 8),
                    Decimal(str(rng.choice((0, 0, 0, 0.05, 0.1, 0.15, 0.2)))),
                )
            )

    cur.executemany(
        """
        INSERT INTO orders (
            order_id, customer_id, employee_id, order_date, required_date,
            shipped_date, ship_via, freight, ship_name, ship_address, ship_city,
            ship_region, ship_postal_code, ship_country
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        order_rows,
    )
    cur.executemany(
        """
        INSERT INTO order_details (order_id, product_id, unit_price, quantity, discount)
        VALUES (%s, %s, %s, %s, %s)
        """,
        detail_rows,
    )
    cur.execute(
        """
        INSERT INTO northwind_data_provenance (
            seed_version, source_type, description, order_count, order_detail_count,
            period_start, period_end
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (
            SEED_VERSION,
            "synthetic_northwind_native",
            "Deterministic operational delta generated from existing Northwind customers, products, employees, and shippers.",
            len(order_rows),
            len(detail_rows),
            START_DATE,
            END_DATE,
        ),
    )
    print(
        f"seeded Northwind operational delta: {len(order_rows)} orders, "
        f"{len(detail_rows)} order details"
    )
    return len(order_rows), len(detail_rows)
