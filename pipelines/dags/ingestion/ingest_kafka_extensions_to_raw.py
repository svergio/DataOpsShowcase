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
    description="Kafka extension topics (marketing, SEO, HR, feature flags) -> raw.kafka_extension_events",
    schedule=SCHEDULE,
    start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    default_args=default_args(),
    tags=["ingestion", "kafka", "extensions"],
)
def ingest_kafka_extensions_to_raw() -> None:
    @task(retries=3)
    def ext_marketing() -> dict:
        return _consume_one("marketing_email")

    @task(retries=3)
    def ext_seo() -> dict:
        return _consume_one("seo_organic")

    @task(retries=3)
    def ext_hr() -> dict:
        return _consume_one("hr_time_tracking")

    @task(retries=3)
    def ext_flags() -> dict:
        return _consume_one("feature_flag_eval")

    @task(outlets=[DS_RAW_KAFKA_EXTENSIONS])
    def seal_extensions(marketing: dict, seo: dict, hr: dict, flags: dict) -> dict:
        return {"dag": DAG_ID, "status": "published", "stats": [marketing, seo, hr, flags]}

    seal_extensions(ext_marketing(), ext_seo(), ext_hr(), ext_flags())


dag = ingest_kafka_extensions_to_raw()
