import os
import runpy
from pathlib import Path

import psycopg
import pytest

from app import config
from scripts import seed_dev


@pytest.mark.parametrize("app_env,expected", [
    ("development", ("admin.local@example.com", "viewer.local@example.com")),
    ("production", ("admin@example.com", "viewer@example.com")),
])
def test_account_defaults_are_separate(monkeypatch, app_env, expected):
    monkeypatch.setenv("APP_ENV", app_env)
    monkeypatch.delenv("ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("VIEWER_EMAIL", raising=False)
    settings = runpy.run_path(str(Path(config.__file__)))
    assert (settings["ADMIN_EMAIL"], settings["VIEWER_EMAIL"]) == expected


def test_configured_email_is_normalized(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", " Admin.Custom@Example.com ")
    settings = runpy.run_path(str(Path(config.__file__)))
    assert settings["ADMIN_EMAIL"] == "admin.custom@example.com"


@pytest.fixture
def account_cursor(monkeypatch):
    # Temporary tables shadow public.users; all test data is rolled back.
    if not os.getenv("DATABASE_URL"):
        pytest.skip("Account SQL checks require DATABASE_URL")
    with psycopg.connect(config.DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE TEMP TABLE users (id TEXT PRIMARY KEY, tenant_id TEXT, email TEXT UNIQUE, password_hash TEXT, role TEXT)")
            monkeypatch.setattr(seed_dev, "hash_password", lambda _: "test-hash")
            try:
                yield cur
            finally:
                conn.rollback()


@pytest.mark.parametrize("user_id,role", [("user_admin", "admin"), ("user_viewer", "viewer")])
def test_rename_keeps_identity_role_and_password(account_cursor, monkeypatch, user_id, role):
    seed_dev.seed_user(account_cursor, user_id, f"{role}@example.com", "test-only", role)
    monkeypatch.setattr(seed_dev, "hash_password", lambda _: pytest.fail("Existing password must not be replaced"))
    for _ in range(2):
        seed_dev.seed_user(account_cursor, user_id, f"{role}.local@example.com", "ignored", role)
    account_cursor.execute("SELECT id,tenant_id,email,password_hash,role FROM users")
    assert account_cursor.fetchall() == [(user_id, seed_dev.TENANT_ID, f"{role}.local@example.com", "test-hash", role)]


def test_email_owned_by_another_user_is_rejected(account_cursor):
    seed_dev.seed_user(account_cursor, "other", "occupied@example.com", "test-only", "admin")
    with pytest.raises(RuntimeError, match="another user"):
        seed_dev.seed_user(account_cursor, "user_admin", "occupied@example.com", "ignored", "admin")
    account_cursor.execute("SELECT id FROM users")
    assert account_cursor.fetchall() == [("other",)]


def test_wrong_role_is_not_changed(account_cursor):
    seed_dev.seed_user(account_cursor, "user_admin", "old@example.com", "test-only", "viewer")
    with pytest.raises(RuntimeError, match="tenant or role"):
        seed_dev.seed_user(account_cursor, "user_admin", "new@example.com", "ignored", "admin")
    account_cursor.execute("SELECT email,role FROM users")
    assert account_cursor.fetchone() == ("old@example.com", "viewer")


def test_invalid_email_is_rejected(account_cursor):
    with pytest.raises(RuntimeError, match="email address"):
        seed_dev.seed_user(account_cursor, "user_admin", "", "ignored", "admin")
