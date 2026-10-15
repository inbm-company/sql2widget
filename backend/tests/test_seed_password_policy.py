"""Production administrator passwords use the explicitly configured value."""

import pytest

from scripts import seed_dev


@pytest.fixture
def production_settings(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_SECRET", "s" * 32)
    monkeypatch.setattr(seed_dev, "VIEWER_PASSWORD", "v" * 16)


def test_short_admin_password_with_special_character_is_accepted(production_settings, monkeypatch):
    monkeypatch.setattr(seed_dev, "ADMIN_PASSWORD", "short!")
    seed_dev.validate_production_settings()


@pytest.mark.parametrize("password", ["", "   ", "demo-password"])
def test_empty_or_development_admin_password_is_rejected(production_settings, monkeypatch, password):
    monkeypatch.setattr(seed_dev, "ADMIN_PASSWORD", password)
    with pytest.raises(RuntimeError, match="non-empty, non-default ADMIN_PASSWORD"):
        seed_dev.validate_production_settings()


def test_viewer_password_policy_is_preserved(production_settings, monkeypatch):
    monkeypatch.setattr(seed_dev, "ADMIN_PASSWORD", "short!")
    monkeypatch.setattr(seed_dev, "VIEWER_PASSWORD", "short!")
    with pytest.raises(RuntimeError, match="VIEWER_PASSWORD"):
        seed_dev.validate_production_settings()


def test_application_secret_policy_is_preserved(production_settings, monkeypatch):
    monkeypatch.setattr(seed_dev, "ADMIN_PASSWORD", "short!")
    monkeypatch.setenv("APP_SECRET", "s" * 31)
    with pytest.raises(RuntimeError, match="APP_SECRET"):
        seed_dev.validate_production_settings()
