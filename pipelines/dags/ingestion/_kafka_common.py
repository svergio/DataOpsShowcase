from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from services.common.config_loader import load_yaml
from services.common.logging_utils import get_logger
from services.common.metrics import record_ingestion_lag, record_kafka_offset_lag
from services.common.run_metadata import finish_run, start_run
from services.common.watermarks import get_kafka_offsets, set_kafka_offsets
from services.kafka.microbatch_consumer import MicroBatchKafkaConsumer
from services.storage.postgres_io import bulk_insert

logger = get_logger(__name__)


def _resolve_topic(topic_env: str) -> str:
    topic = os.environ.get(topic_env)
    if not topic:
        raise RuntimeError(f"env {topic_env} is not configured")
    return topic


def _to_ts(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def consume_topic(
    *,
    dag_id: str,
    task_id: str,
    pipeline_name: str,
    source: str,
    topic_key: str,
    record_builder,
    target_table: str,
    insert_columns: list[str],
) -> dict[str, Any]:
    cfg = load_yaml("ingestion")["kafka"]
    topic_cfg = cfg["topics"][topic_key]
    topic = _resolve_topic(topic_cfg["topic_env"])
    bootstrap = os.environ.get(cfg["bootstrap_servers_env"], "kafka:9092")
    group_id = f"{cfg['consumer_group_prefix']}-{topic_key}"
    max_messages = int(cfg.get("max_messages_per_run", 5000))
    poll_timeout = float(cfg.get("poll_timeout_seconds", 5))
    max_empty_polls = int(cfg.get("max_empty_polls", 3))
    run_meta = start_run(
        dag_id=dag_id,
        task_id=task_id,
        source=source,
        layer="ingestion",
        payload={"topic": topic, "group_id": group_id},
    )
    try:
        offsets = get_kafka_offsets(pipeline_name)
        with MicroBatchKafkaConsumer(
            topic=topic,
            group_id=group_id,
            bootstrap_servers=bootstrap,
            max_messages=max_messages,
            poll_timeout=poll_timeout,
            max_empty_polls=max_empty_polls,
        ) as consumer:
            consumer.seek_to_offsets(offsets)
            batch = consumer.fetch()
            if not batch.messages:
                finish_run(run_meta, status="success", rows_in=0, rows_out=0)
                return {"topic": topic, "messages": 0, "offsets": offsets}
            msg_count = len(batch.messages)
            rows = []
            for msg in batch.messages:
                built = record_builder(msg)
                if built is not None:
                    rows.append(built)
            inserted = bulk_insert(
                "postgres_dwh",
                target_table,
                insert_columns,
                rows,
                page_size=1000,
                on_conflict="ON CONFLICT (topic, partition_id, kafka_offset) DO NOTHING",
            )
            new_offsets = {**offsets, **batch.last_offsets}
            consumer.commit_offsets(batch.last_offsets)
            set_kafka_offsets(pipeline_name, new_offsets, records_processed=inserted)
            try:
                high = consumer.get_high_watermarks()
                for partition, high_offset in high.items():
                    last = int(new_offsets.get(partition, -1))
                    lag = max(0, int(high_offset) - max(last + 1, 0))
                    record_kafka_offset_lag(topic=topic, partition=int(partition), lag=lag)
            except Exception:  # noqa: BLE001
                pass
            try:
                latest_ts: datetime | None = None
                for msg in batch.messages:
                    ts = _to_ts(msg.timestamp_ms / 1000.0) if msg.timestamp_ms else None
                    if ts and (latest_ts is None or ts > latest_ts):
                        latest_ts = ts
                if latest_ts:
                    lag_seconds = (datetime.now(timezone.utc) - latest_ts).total_seconds()
                    record_ingestion_lag(pipeline=pipeline_name, lag_seconds=lag_seconds)
            except Exception:  # noqa: BLE001
                pass
        finish_run(
            run_meta,
            status="success",
            rows_in=msg_count,
            rows_out=inserted,
            payload={
                "offsets": new_offsets,
                "kafka_messages_in_batch": msg_count,
                "rows_after_filter": len(rows),
            },
        )
        return {
            "topic": topic,
            "messages": msg_count,
            "offsets": new_offsets,
            "rows_inserted": inserted,
        }
    except Exception as exc:
        finish_run(run_meta, status="failed", error_message=str(exc))
        raise


def order_record_builder(msg) -> tuple:
    payload = msg.value or {}
    event_ts = _to_ts(payload.get("event_ts") or payload.get("ts"))
    return (
        msg.topic,
        msg.partition,
        msg.offset,
        payload.get("event_id"),
        payload.get("event_type"),
        payload.get("order_id"),
        payload.get("customer_id") or payload.get("user_id"),
        payload.get("total_amount") or payload.get("amount"),
        (payload.get("currency") or "")[:3] or None,
        (payload.get("country_code") or "")[:2] or None,
        json.dumps(payload, default=str, ensure_ascii=False),
        event_ts,
    )


def payment_record_builder(msg) -> tuple:
    payload = msg.value or {}
    event_ts = _to_ts(payload.get("event_ts") or payload.get("ts"))
    return (
        msg.topic,
        msg.partition,
        msg.offset,
        payload.get("event_id"),
        payload.get("event_type"),
        payload.get("payment_id"),
        payload.get("order_id"),
        payload.get("transaction_id"),
        payload.get("amount"),
        (payload.get("currency") or "")[:3] or None,
        payload.get("payment_method"),
        payload.get("status"),
        payload.get("decline_reason"),
        json.dumps(payload, default=str, ensure_ascii=False),
        event_ts,
    )


def extension_record_builder(msg, *, domain_code: str) -> tuple | None:
    raw = getattr(msg, "value", None)
    if isinstance(raw, dict):
        payload = raw
    elif isinstance(raw, (bytes, bytearray)):
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = {}
    elif isinstance(raw, str):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {}
    else:
        payload = {}
    evt = (
        payload.get("event_timestamp")
        or payload.get("event_ts")
        or payload.get("timestamp")
        or payload.get("ts")
    )
    event_ts = _to_ts(evt)
    if event_ts is None and isinstance(evt, (int, float)):
        ts_f = float(evt)
        event_ts = _to_ts(ts_f / 1000.0) if ts_f > 1e12 else _to_ts(ts_f)
    if event_ts is None and getattr(msg, "timestamp_ms", None):
        event_ts = _to_ts(float(msg.timestamp_ms) / 1000.0)
    part = getattr(msg, "partition", None)
    off = getattr(msg, "offset", None)
    if part is None or off is None:
        logger.warning(
            "skipping extension message without partition/offset",
            extra={
                "extra_payload": {
                    "domain_code": domain_code,
                    "topic": getattr(msg, "topic", None),
                }
            },
        )
        return None
    eid = payload.get("event_id")
    top = getattr(msg, "topic", None) or ""
    return (
        top,
        int(part),
        int(off),
        domain_code,
        str(eid) if eid is not None else None,
        payload.get("event_type"),
        json.dumps(payload, default=str, ensure_ascii=False),
        event_ts,
    )
