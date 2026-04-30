from __future__ import annotations

from types import SimpleNamespace

from pipelines.dags.ingestion._kafka_common import extension_record_builder


def test_extension_record_builder_returns_row() -> None:
    msg = SimpleNamespace(
        topic="events.marketing",
        partition=2,
        offset=99,
        value={"event_id": "e1", "event_type": "open", "event_ts": "2026-01-15T10:00:00+00:00"},
        timestamp_ms=None,
    )
    row = extension_record_builder(msg, domain_code="marketing_email")
    assert row is not None
    assert row[0] == "events.marketing"
    assert row[1] == 2
    assert row[2] == 99
    assert row[3] == "marketing_email"
    assert row[4] == "e1"
    assert row[5] == "open"
    assert row[7] is not None


def test_extension_record_builder_ms_timestamp_in_payload() -> None:
    msg = SimpleNamespace(
        topic="t",
        partition=0,
        offset=1,
        value={"event_id": "x", "ts": 1_700_000_000_000.0},
        timestamp_ms=None,
    )
    row = extension_record_builder(msg, domain_code="hr_time_tracking")
    assert row is not None
    assert row[7] is not None


def test_extension_record_builder_none_without_partition() -> None:
    msg = SimpleNamespace(
        topic="t",
        partition=None,
        offset=0,
        value={},
        timestamp_ms=None,
    )
    assert extension_record_builder(msg, domain_code="feature_flag_eval") is None


def test_extension_record_builder_none_without_offset() -> None:
    msg = SimpleNamespace(
        topic="t",
        partition=0,
        offset=None,
        value={},
        timestamp_ms=None,
    )
    assert extension_record_builder(msg, domain_code="seo_organic") is None
