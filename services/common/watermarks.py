from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from airflow.providers.postgres.hooks.postgres import PostgresHook

from services.common.config_loader import load_yaml
from services.common.logging_utils import get_logger

logger = get_logger(__name__)

DEFAULT_FALLBACK_TS = "1970-01-01T00:00:00+00:00"


def _conn_id() -> str:
    cfg = load_yaml("watermarks").get("storage", {})
    return cfg.get("conn_id", "postgres_dwh")


def _table() -> str:
    cfg = load_yaml("watermarks").get("storage", {})
    return cfg.get("table", "meta.pipeline_watermarks")


@contextmanager
def _cursor() -> Iterator[Any]:
    hook = PostgresHook(postgres_conn_id=_conn_id())
    conn = hook.get_conn()
    try:
        with conn.cursor() as cursor:
            yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_watermark(pipeline_name: str, *, fallback: str | None = None) -> str:
    sql = f"SELECT watermark_value FROM {_table()} WHERE pipeline_name = %s"
    with _cursor() as cur:
        cur.execute(sql, (pipeline_name,))
        row = cur.fetchone()
    if row and row[0]:
        return row[0]
    return fallback if fallback is not None else DEFAULT_FALLBACK_TS


def set_watermark(
    pipeline_name: str,
    value: str,
    *,
    records_processed: int | None = None,
    notes: str | None = None,
) -> None:
    sql = f"""
        INSERT INTO {_table()} (pipeline_name, watermark_value, last_run_at, records_processed, notes)
        VALUES (%s, %s, NOW(), %s, %s)
        ON CONFLICT (pipeline_name) DO UPDATE SET
            watermark_value = EXCLUDED.watermark_value,
            last_run_at = EXCLUDED.last_run_at,
            records_processed = EXCLUDED.records_processed,
            notes = EXCLUDED.notes
    """
    with _cursor() as cur:
        cur.execute(sql, (pipeline_name, value, records_processed, notes))
    logger.info(
        "watermark updated",
        extra={
            "extra_payload": {
                "pipeline": pipeline_name,
                "watermark": value,
                "records_processed": records_processed,
            }
        },
    )


def get_kafka_offsets(pipeline_name: str) -> dict[int, int]:
    raw = get_watermark(pipeline_name, fallback="{}")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return {int(k): int(v) for k, v in data.items()}


def set_kafka_offsets(pipeline_name: str, offsets: dict[int, int], records_processed: int | None = None) -> None:
    serialized = json.dumps({str(k): int(v) for k, v in offsets.items()})
    set_watermark(pipeline_name, serialized, records_processed=records_processed)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
