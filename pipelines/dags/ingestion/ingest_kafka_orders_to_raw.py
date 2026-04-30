from __future__ import annotations

from datetime import datetime, timezone

from airflow.decorators import dag, task

from pipelines.dags.ingestion._kafka_common import (
    consume_topic,
    order_record_builder,
)
from pipelines.utils.dag_factory import default_args
from pipelines.utils.datasets import DS_RAW_KAFKA_ORDERS
from pipelines.utils.dbt_web_webhook import EVENT_INGESTION_COMPLETED, notify_dbt_web

DAG_ID = "dag_ingest_kafka_orders_to_raw"
SCHEDULE = "*/5 * * * *"

ORDER_INSERT_COLUMNS = [
    "topic",
    "partition_id",
    "kafka_offset",
    "event_id",
    "event_type",
    "order_id",
    "customer_id",
    "total_amount",
    "currency",
    "country_code",
    "payload",
    "event_ts",
]


@dag(
    dag_id=DAG_ID,
    description="Kafka orders -> raw.kafka_orders micro-batch ingestion with offset watermarks",
    schedule=SCHEDULE,
    start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    default_args=default_args(),
    tags=["ingestion", "kafka", "orders"],
)
def ingest_kafka_orders_to_raw() -> None:
    @task(retries=3)
    def consume() -> dict:
        return consume_topic(
            dag_id=DAG_ID,
            task_id="consume",
            pipeline_name="kafka.orders",
            source="kafka.orders",
            topic_key="orders",
            record_builder=order_record_builder,
            target_table="raw.kafka_orders",
            insert_columns=ORDER_INSERT_COLUMNS,
        )

    @task(outlets=[DS_RAW_KAFKA_ORDERS])
    def publish(stats: dict, airflow_run_ref: str = "{{ run_id }}") -> dict:
        from services.common.logging_utils import get_logger

        get_logger(DAG_ID).info(
            "kafka.orders raw signal",
            extra={"extra_payload": stats},
        )
        notify_dbt_web(
            event=EVENT_INGESTION_COMPLETED,
            dag_id=DAG_ID,
            run_id=airflow_run_ref,
            target_layer="raw.kafka_orders",
        )
        return {"dag": DAG_ID, "status": "published", **stats}

    publish(consume())


dag = ingest_kafka_orders_to_raw()
