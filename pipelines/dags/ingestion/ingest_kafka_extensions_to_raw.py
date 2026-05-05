from __future__ import annotations

from datetime import datetime, timezone
from functools import partial

from airflow.decorators import dag, task

from pipelines.dags.ingestion._kafka_common import consume_topic, extension_record_builder
from pipelines.utils.dag_factory import default_args
from pipelines.utils.datasets import DS_RAW_KAFKA_EXTENSIONS

DAG_ID = "dag_ingest_kafka_extensions_to_raw"
SCHEDULE = "*/5 * * * *"

EXTENSION_INSERT_COLUMNS = [
    "topic",
    "partition_id",
    "kafka_offset",
    "domain_code",
    "event_id",
    "event_type",
    "payload",
    "event_ts",
]


def _consume_one(topic_key: str) -> dict:
    from services.common.config_loader import load_yaml

    cfg_root = load_yaml("ingestion")
    tc = cfg_root["kafka"]["topics"][topic_key]
    dc = tc["domain_code"]
    tgt = tc["target_table"]
    return consume_topic(
        dag_id=DAG_ID,
        task_id=f"consume_{topic_key}",
        pipeline_name=f"kafka.extensions.{topic_key}",
        source=f"kafka.extensions.{topic_key}",
        topic_key=topic_key,
        record_builder=partial(extension_record_builder, domain_code=dc),
        target_table=tgt,
        insert_columns=EXTENSION_INSERT_COLUMNS,
    )


@dag(
    dag_id=DAG_ID,
    description="Kafka extension topics -> raw.kafka_extension_events (partial topic failures tolerated)",
    schedule=SCHEDULE,
    start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    default_args=default_args(),
    tags=["ingestion", "kafka", "extensions"],
)
def ingest_kafka_extensions_to_raw() -> None:
    @task(retries=1)
    def consume_extensions_consolidated() -> dict:
        from services.common.config_loader import load_yaml
        from services.common.logging_utils import get_logger

        cfg_root = load_yaml("ingestion")
        ext_cfg = cfg_root.get("kafka", {}).get("extensions") or {}
        keys = list(ext_cfg.get("topic_keys") or [])
        if not keys:
            keys = ["marketing_email", "seo_organic", "hr_time_tracking", "feature_flag_eval"]
        min_ok = int(ext_cfg.get("min_success_count", 1))
        stats: list[dict] = []
        errors: list[dict] = []
        for topic_key in keys:
            try:
                stats.append(_consume_one(topic_key))
            except Exception as exc:  # noqa: BLE001
                errors.append({"topic_key": topic_key, "error": str(exc).replace("\n", " ")[:600]})

        if len(stats) < min_ok:
            raise RuntimeError(
                f"extensions ingest: only {len(stats)} topic(s) succeeded (min_success_count={min_ok}); "
                f"errors={errors}"
            )

        if errors:
            get_logger(DAG_ID).warning(
                "extensions partial failures",
                extra={"extra_payload": {"ok": len(stats), "errors": errors}},
            )

        return {"stats": stats, "errors": errors, "ok_count": len(stats)}

    @task(outlets=[DS_RAW_KAFKA_EXTENSIONS])
    def seal_extensions(payload: dict) -> dict:
        return {"dag": DAG_ID, "status": "published", **payload}

    seal_extensions(consume_extensions_consolidated())


dag = ingest_kafka_extensions_to_raw()
