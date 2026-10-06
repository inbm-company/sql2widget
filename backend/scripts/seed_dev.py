#!/usr/bin/env python3
"""Seed demo tenant, admin user, DB connection, permissions, docs."""

import secrets
import os

import psycopg

from app.auth import hash_password
from app.config import (
    ADMIN_EMAIL,
    VIEWER_EMAIL,
    DATABASE_URL,
    DEMO_CUSTOMER_DATABASE_URL,
    NORTHWIND_DATABASE_URL,
    STAGE_GLOBAL_DATABASE_URL,
)
from app.repositories import connections as conn_repo

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "demo-password")
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
    "customer_customer_demo",
    "customer_demographics",
    "customers",
    "employee_territories",
    "employees",
    "northwind_data_provenance",
    "order_details",
    "orders",
    "products",
    "region",
    "shippers",
    "suppliers",
    "territories",
    "us_states",
]


def seed_user(cur, user_id: str, email: str, password: str, role: str) -> None:
    """Keep the seeded identity and password when changing its login email."""
    if not email or "@" not in email:
        raise RuntimeError("Seed account email must be a non-empty email address")
    cur.execute("SELECT id FROM users WHERE email = %s", (email,))
    owner = cur.fetchone()
    if owner and owner[0] != user_id:
        raise RuntimeError("Seed account email already belongs to another user")
    cur.execute("SELECT tenant_id, role FROM users WHERE id = %s", (user_id,))
    existing = cur.fetchone()
    if existing:
        if existing != (TENANT_ID, role):
            raise RuntimeError("Existing seed account has a different tenant or role")
        cur.execute("UPDATE users SET email = %s WHERE id = %s AND email <> %s", (email, user_id, email))
    else:
        cur.execute(
            "INSERT INTO users (id, tenant_id, email, password_hash, role) VALUES (%s, %s, %s, %s, %s)",
            (user_id, TENANT_ID, email, hash_password(password), role),
        )


def main() -> None:
    if ADMIN_EMAIL == VIEWER_EMAIL:
        raise RuntimeError("Admin and viewer must use different email addresses")
    if os.getenv("APP_ENV") == "production" and (
        len(ADMIN_PASSWORD) < 16 or len(VIEWER_PASSWORD) < 16
        or len(os.getenv("APP_SECRET", "")) < 32
    ):
        raise RuntimeError("Production requires strong ADMIN_PASSWORD, VIEWER_PASSWORD and APP_SECRET")
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
            seed_user(cur, USER_ID, ADMIN_EMAIL, ADMIN_PASSWORD, "admin")
            seed_user(cur, VIEWER_ID, VIEWER_EMAIL, VIEWER_PASSWORD, "viewer")

            for user_id in (USER_ID, VIEWER_ID):
                cur.execute(
                    """
                    INSERT INTO projects (id, tenant_id, user_id, title)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (f"prj_default_{user_id}", TENANT_ID, user_id, "디폴트"),
                )

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
