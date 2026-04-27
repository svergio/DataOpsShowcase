from __future__ import annotations

from datetime import datetime, timezone

from lib_runtime import execution_slug, parse_execution_ts, safe_table_token


def test_parse_execution_ts_with_z() -> None:
    dt = parse_execution_ts("2026-01-15T10:00:00Z")
    assert dt.tzinfo is not None
    assert dt.year == 2026
    assert dt.month == 1


def test_execution_slug_utc() -> None:
    dt = datetime(2026, 4, 1, 12, 30, 0, tzinfo=timezone.utc)
    s = execution_slug(dt)
    assert s.startswith("20260401")


def test_safe_table_token() -> None:
    assert safe_table_token("staging.stg_orders") == "staging_stg_orders"
