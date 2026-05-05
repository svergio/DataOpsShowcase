from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from services.common.config_loader import load_yaml
from services.common.logging_utils import get_logger
from services.common.redis_client import RedisConfig, build_client
from services.common.watermarks import set_watermark
from services.storage.postgres_io import fetch_one, upsert

logger = get_logger(__name__)


@dataclass(frozen=True)
class ServingMetric:
    metric_key: str
    value_type: str
    redis_key: str
    sql: str


def _as_num(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _load_metrics() -> tuple[str, str, str, list[ServingMetric]]:
    cfg = load_yaml("serving").get("redis_serving", {})
    redis_url = os.environ.get(cfg.get("redis_url_env", "REDIS_URL"), cfg.get("redis_url_default", "redis://redis:6379/0"))
    key_prefix = str(cfg.get("key_prefix", "techmart:serving"))
    snapshot_table = str(cfg.get("snapshot_table", "dwh_marts.redis_serving_snapshot"))
    metrics = [
        ServingMetric(
            metric_key=str(item["metric_key"]),
            value_type=str(item.get("value_type", "numeric")),
            redis_key=str(item["redis_key"]),
            sql=str(item["sql"]),
        )
        for item in cfg.get("metrics", [])
    ]
    return redis_url, key_prefix, snapshot_table, metrics


def materialize_redis_and_snapshot(conn_id: str = "postgres_dwh") -> dict[str, Any]:
    redis_url, key_prefix, snapshot_table, metrics = _load_metrics()
    if not metrics:
        return {"processed": 0}

    now = datetime.now(timezone.utc)
    rows: list[tuple[Any, ...]] = []
    processed = 0

    redis_client = build_client(RedisConfig(url=redis_url))
    try:
        for metric in metrics:
            row = fetch_one(conn_id, metric.sql)
            value = row[0] if row else None
            redis_key = f"{key_prefix}:{metric.redis_key}"

            metric_value_num: Decimal | None = None
            metric_value_text: str | None = None
            if metric.value_type == "numeric":
                metric_value_num = _as_num(value)
                redis_client.set(redis_key, str(metric_value_num or Decimal("0")))
            elif metric.value_type == "integer":
                metric_value_num = _as_num(value)
                redis_client.set(redis_key, str(int(metric_value_num or 0)))
            else:
                metric_value_text = str(value or "")
                redis_client.set(redis_key, metric_value_text)

            rows.append((metric.metric_key, metric_value_num, metric_value_text, metric.sql, now))
            processed += 1

        upsert(
            conn_id=conn_id,
            table=snapshot_table,
            columns=["metric_key", "metric_value_num", "metric_value_text", "source_sql", "updated_at"],
            rows=rows,
            conflict_columns=["metric_key"],
            update_columns=["metric_value_num", "metric_value_text", "source_sql", "updated_at"],
        )
        set_watermark("serving.redis", now.isoformat(), records_processed=processed)
        logger.info(
            "redis serving materialized",
            extra={"extra_payload": {"processed": processed, "snapshot_table": snapshot_table}},
        )
        return {"processed": processed, "snapshot_table": snapshot_table}
    finally:
        redis_client.close()
