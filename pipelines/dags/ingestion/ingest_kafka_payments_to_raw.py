from __future__ import annotations

from datetime import datetime, timezone

from airflow.decorators import dag, task

from pipelines.dags.ingestion._kafka_common import (
    consume_topic,
    payment_record_builder,
)
from pipelines.utils.dag_factory import default_args
from pipelines.utils.datasets import DS_RAW_KAFKA_PAYMENTS

DAG_ID = "dag_ingest_kafka_payments_to_raw"
SCHEDULE = "*/5 * * * *"

PAYMENT_INSERT_COLUMNS = [
    "topic",
    "partition_id",
    "kafka_offset",
    "event_id",
    "event_type",
    "payment_id",
    "order_id",
    "transaction_id",
    "amount",
    "currency",
    "payment_method",
    "status",
    "decline_reason",
    "payload",
    "event_ts",
]


@dag(
    dag_id=DAG_ID,
    description="Kafka payments -> raw.kafka_payments micro-batch ingestion with offset watermarks",
    schedule=SCHEDULE,
    start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    default_args=default_args(),
    tags=["ingestion", "kafka", "payments"],
)
def ingest_kafka_payments_to_raw() -> None:
    @task(retries=3)
    def consume() -> dict:
        return consume_topic(
            dag_id=DAG_ID,
            task_id="consume",
            pipeline_name="kafka.payments",
            source="kafka.payments",
            topic_key="payments",
            record_builder=payment_record_builder,
            target_table="raw.kafka_payments",
            insert_columns=PAYMENT_INSERT_COLUMNS,
        )

    @task(outlets=[DS_RAW_KAFKA_PAYMENTS])
    def publish(stats: dict, airflow_run_ref: str = "{{ run_id }}") -> dict:
        from services.common.logging_utils import get_logger

        get_logger(DAG_ID).info(
            "kafka.payments raw signal",
            extra={"extra_payload": stats},
        )
        return {"dag": DAG_ID, "status": "published", **stats}

    publish(consume())


dag = ingest_kafka_payments_to_raw()
