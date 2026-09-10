#!/usr/bin/env python3
"""Seed demo tenant, admin user, DB connection, permissions, docs."""

import secrets
import os

import psycopg

from app.auth import hash_password
from app.config import (
    DATABASE_URL,
    DEMO_CUSTOMER_DATABASE_URL,
    NORTHWIND_DATABASE_URL,
    STAGE_GLOBAL_DATABASE_URL,
)
from app.repositories import connections as conn_repo

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "demo-password")
VIEWER_EMAIL = "viewer@example.com"
VIEWER_PASSWORD = os.getenv("VIEWER_PASSWORD", "demo-password")
TENANT_ID = "tenant_demo"
USER_ID = "user_admin"
VIEWER_ID = "user_viewer"
DEMO_TABLES = [
    "servers",
    "attack_events",
    "incidents",
    "vulnerability_findings",
    "blocked_ips",
]
GLOBAL_TABLES = ["regions", "products", "monthly_sales"]
NORTHWIND_TABLES = [
    "categories",
    "customers",
    "employees",
    "products",
    "orders",
    "order_details",
]


def main() -> None:
    if os.getenv("APP_ENV") == "production" and (
        len(ADMIN_PASSWORD) < 16 or len(VIEWER_PASSWORD) < 16
        or len(os.getenv("APP_SECRET", "")) < 32
    ):
        raise RuntimeError("Production requires strong ADMIN_PASSWORD, VIEWER_PASSWORD and APP_SECRET")
    password_hash = hash_password(ADMIN_PASSWORD)
    viewer_hash = hash_password(VIEWER_PASSWORD)
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tenants (id, name)
                VALUES (%s, %s)
                ON CONFLICT (id) DO NOTHING
                """,
                (TENANT_ID, "Demo Tenant"),
            )
            cur.execute("SELECT id FROM users WHERE email = %s", (ADMIN_EMAIL,))
            existing = cur.fetchone()
            if existing:
                print(f"user exists: {ADMIN_EMAIL}")
            else:
                cur.execute(
                    """
                    INSERT INTO users (id, tenant_id, email, password_hash, role)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (USER_ID, TENANT_ID, ADMIN_EMAIL, password_hash, "admin"),
                )
                print(f"created user {ADMIN_EMAIL}")

            cur.execute("SELECT id FROM users WHERE email = %s", (VIEWER_EMAIL,))
            viewer_existing = cur.fetchone()
            if viewer_existing:
                print(f"user exists: {VIEWER_EMAIL}")
            else:
                cur.execute(
                    """
                    INSERT INTO users (id, tenant_id, email, password_hash, role)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (VIEWER_ID, TENANT_ID, VIEWER_EMAIL, viewer_hash, "viewer"),
                )
                print(f"created user {VIEWER_EMAIL}")

            # document chunks for RAG scaffold
            cur.execute(
                "SELECT 1 FROM document_chunks WHERE tenant_id = %s LIMIT 1",
                (TENANT_ID,),
            )
            if not cur.fetchone():
                docs = [
                    (
                        "doc_ssh",
                        "SSH Hardening Guide",
                        "1.4",
                        "3.2 Brute force",
                        "SSH 무차별 대입 완화: fail2ban, 키 인증, 관리 대역 제한.",
                    ),
                    (
                        "doc_ransomware",
                        "Incident Playbook",
                        "2.0",
                        "Ransomware",
                        "랜섬웨어: 격리, 백업 검증, 세그먼트 분리.",
                    ),
                ]
                for doc_id, title, version, section, content in docs:
                    cur.execute(
                        """
                        INSERT INTO document_chunks (
                            id, tenant_id, doc_id, title, version, section, content
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s)
                        """,
                        (
                            f"chunk_{secrets.token_hex(6)}",
                            TENANT_ID,
                            doc_id,
                            title,
                            version,
                            section,
                            content,
                        ),
                    )
                print("seeded document_chunks")
        conn.commit()

    table_rows = [{"schema_name": "public", "table_name": t} for t in DEMO_TABLES]
    global_rows = [{"schema_name": "public", "table_name": t} for t in GLOBAL_TABLES]

    try:
        conn_repo.upsert_from_url(
            tenant_id=TENANT_ID,
            name="SOC Customer DB",
            url=DEMO_CUSTOMER_DATABASE_URL,
            created_by=USER_ID,
            connection_id="dbconn_demo",
        )
        for role in ("admin", "user", "viewer"):
            conn_repo.replace_table_permissions(
                tenant_id=TENANT_ID,
                connection_id="dbconn_demo",
                role=role,
                tables=table_rows,
            )
        print("seeded dbconn_demo + table permissions")
    except Exception as exc:  # noqa: BLE001
        print(f"SOC connection seed skipped/failed: {exc}")

    try:
        conn_repo.upsert_from_url(
            tenant_id=TENANT_ID,
            name="Global Sales DB",
            url=STAGE_GLOBAL_DATABASE_URL,
            created_by=USER_ID,
            connection_id="dbconn_global",
        )
        for role in ("admin", "user", "viewer"):
            conn_repo.replace_table_permissions(
                tenant_id=TENANT_ID,
                connection_id="dbconn_global",
                role=role,
                tables=global_rows,
            )
        print("seeded dbconn_global + table permissions")
    except Exception as exc:  # noqa: BLE001
        print(f"global connection seed skipped/failed: {exc}")

    try:
        conn_repo.upsert_from_url(
            tenant_id=TENANT_ID,
            name="Northwind Sample DB",
            url=NORTHWIND_DATABASE_URL,
            created_by=USER_ID,
            connection_id="dbconn_northwind",
        )
        northwind_rows = [
            {"schema_name": "public", "table_name": table}
            for table in NORTHWIND_TABLES
        ]
        for role in ("admin", "user", "viewer"):
            conn_repo.replace_table_permissions(
                tenant_id=TENANT_ID,
                connection_id="dbconn_northwind",
                role=role,
                tables=northwind_rows,
            )
        print("seeded dbconn_northwind + table permissions")
    except Exception as exc:  # noqa: BLE001
        print(f"northwind connection seed skipped/failed: {exc}")

    print("seed done")


if __name__ == "__main__":
    main()
