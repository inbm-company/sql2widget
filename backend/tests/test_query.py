import json
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from app.query import QueryError, jsonable, validate_readonly_select


def test_select_ok():
    sql = validate_readonly_select(
        "SELECT hostname FROM servers",
        allowed_tables={"servers"},
    )
    assert sql.startswith("SELECT")


def test_rejects_update():
    with pytest.raises(QueryError):
        validate_readonly_select("UPDATE servers SET hostname='x'")


def test_rejects_multi_statement():
    with pytest.raises(QueryError):
        validate_readonly_select("SELECT 1; SELECT 2")


def test_rejects_unknown_table():
    with pytest.raises(QueryError):
        validate_readonly_select(
            "SELECT * FROM secrets",
            allowed_tables={"servers"},
        )


def test_jsonable_decimal_and_dates():
    payload = {
        "revenue": Decimal("12345.67"),
        "units": Decimal("10"),
        "day": date(2026, 8, 1),
        "ts": datetime(2026, 8, 1, 12, 30, 0),
        "id": UUID("12345678-1234-5678-1234-567812345678"),
        "nested": [{"v": Decimal("1.5")}],
    }
    out = jsonable(payload)
    assert out["revenue"] == 12345.67
    assert out["units"] == 10
    assert out["day"] == "2026-08-01"
    assert out["ts"].startswith("2026-08-01T12:30:00")
    assert out["id"] == "12345678-1234-5678-1234-567812345678"
    assert out["nested"][0]["v"] == 1.5
    json.dumps(out)  # must not raise
