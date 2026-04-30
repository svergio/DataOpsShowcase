from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from airflow.decorators import dag, task
from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator

from pipelines.utils.dag_factory import default_args
from pipelines.utils.datasets import (
    DS_RAW_KAFKA_ORDERS,
    DS_RAW_KAFKA_PAYMENTS,
    DS_RAW_MINIO_FILES,
    DS_RAW_OLTP,
    DS_STG_CLEAN,
)

DAG_ID = "dag_spark_preprocess_to_stg"
SOURCE = "spark.preprocess"

SPARK_APPLICATION = "/opt/airflow/spark/jobs/preprocess_orders_payments.py"
SPARK_PY_FILES = (
    "/opt/airflow/spark/common/lib_runtime.py,"
    "/opt/airflow/spark/common/spark_session.py"
)


@dag(
    dag_id=DAG_ID,
    description="Spark preprocessing: cleaning, dedup, schema enforcement, de-anonymization (raw -> stg)",
    schedule=(
        DS_RAW_OLTP
        | DS_RAW_KAFKA_ORDERS
        | DS_RAW_KAFKA_PAYMENTS
        | DS_RAW_MINIO_FILES
    ),
    start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    default_args=default_args(),
    tags=["transformation", "spark", "preprocessing"],
)
def spark_preprocess_to_stg() -> None:
    @task
    def precheck_inputs() -> dict[str, int]:
        from services.common.logging_utils import get_logger
        from services.common.run_metadata import finish_run, start_run
        from services.storage.postgres_io import fetch_one

        run_meta = start_run(
            dag_id=DAG_ID,
            task_id="precheck_inputs",
            source=SOURCE,
            layer="preprocessing",
        )
        try:
            counts = {}
            for table in (
                "raw.oltp_orders",
                "raw.oltp_users",
                "raw.kafka_orders",
                "raw.kafka_payments",
            ):
                row = fetch_one("postgres_dwh", f"SELECT COUNT(*) FROM {table}")
                counts[table] = int(row[0]) if row else 0
            get_logger(DAG_ID).info(
                "spark precheck",
                extra={"extra_payload": counts},
            )
            finish_run(
                run_meta,
                status="success",
                rows_in=sum(counts.values()),
                payload=counts,
            )
            return counts
        except Exception as exc:
            finish_run(run_meta, status="failed", error_message=str(exc))
            raise

    spark_job = SparkSubmitOperator(
        task_id="spark_preprocess",
        application=SPARK_APPLICATION,
        py_files=SPARK_PY_FILES,
        conn_id="spark_default",
        name="dataops_preprocess_orders_payments",
        verbose=False,
        application_args=[
            "--execution-ts",
            "{{ (data_interval_end or logical_date).isoformat() }}",
            "--lookback-hours",
            "{{ var.value.SPARK_PREPROCESS_LOOKBACK_HOURS | default(2) }}",
        ],
        env_vars={
            "DWH_JDBC_URL": os.environ.get(
                "DWH_JDBC_URL",
                "jdbc:postgresql://postgres-dwh:5432/dataops_dwh",
            ),
            "DWH_JDBC_USER": "{{ var.value.DWH_JDBC_USER | default('dataops') }}",
            "DWH_JDBC_PASSWORD": "{{ var.value.DWH_JDBC_PASSWORD | default('dataops') }}",
        },
        conf={
            "spark.jars.packages": "org.postgresql:postgresql:42.7.3",
        },
        retries=3,
        retry_delay=timedelta(minutes=5),
        executor_cores=2,
        executor_memory="1g",
        driver_memory="1g",
        num_executors=1,
    )

    @task
    def validate_stg(raw_counts: dict[str, int]) -> dict[str, int]:
        from services.common.logging_utils import get_logger
        from services.common.run_metadata import finish_run, start_run
        from services.storage.postgres_io import fetch_one

        run_meta = start_run(
            dag_id=DAG_ID,
            task_id="validate_stg",
            source=SOURCE,
            layer="preprocessing",
        )
        try:
            stats: dict[str, int] = {}
            for table in (
                "staging.stg_customers",
                "staging.stg_orders",
                "staging.stg_order_events",
                "staging.stg_payment_events",
            ):
                row = fetch_one("postgres_dwh", f"SELECT COUNT(*) FROM {table}")
                stats[table] = int(row[0]) if row else 0
            log = get_logger(DAG_ID)
            failures: list[str] = []
            if raw_counts.get("raw.oltp_orders", 0) > 0 and stats["staging.stg_orders"] == 0:
                failures.append(
                    "staging.stg_orders is empty but raw.oltp_orders has rows (Spark preprocessing likely failed)"
                )
            if raw_counts.get("raw.oltp_users", 0) > 0 and stats["staging.stg_customers"] == 0:
                failures.append(
                    "staging.stg_customers is empty but raw.oltp_users has rows (Spark preprocessing likely failed)"
                )
            if failures:
                raise ValueError("; ".join(failures))
            if raw_counts.get("raw.kafka_orders", 0) > 0 and stats["staging.stg_order_events"] == 0:
                log.warning(
                    "raw.kafka_orders has rows but staging.stg_order_events is empty after preprocessing",
                    extra={"extra_payload": {"raw_counts": raw_counts, "stats": stats}},
                )
            if raw_counts.get("raw.kafka_payments", 0) > 0 and stats["staging.stg_payment_events"] == 0:
                log.warning(
                    "raw.kafka_payments has rows but staging.stg_payment_events is empty after preprocessing",
                    extra={"extra_payload": {"raw_counts": raw_counts, "stats": stats}},
                )
            if (
                stats["staging.stg_orders"] == 0
                and sum(raw_counts.get(k, 0) for k in raw_counts) == 0
            ):
                log.warning(
                    "staging.stg_orders empty and all precheck raw counts are zero (greenfield or extension-only raw)",
                    extra={"extra_payload": {"raw_counts": raw_counts, "stats": stats}},
                )
            log.info(
                "spark stg validation",
                extra={"extra_payload": {"precheck_counts": raw_counts, "staging_counts": stats}},
            )
            finish_run(
                run_meta,
                status="success",
                rows_out=sum(stats.values()),
                payload={**stats, "precheck_raw": raw_counts},
            )
            return stats
        except Exception as exc:
            finish_run(run_meta, status="failed", error_message=str(exc))
            raise

    @task(outlets=[DS_STG_CLEAN])
    def publish_signal() -> dict:
        from services.common.logging_utils import get_logger

        get_logger(DAG_ID).info(
            "stg clean signal",
            extra={"extra_payload": {"dag": DAG_ID}},
        )
        return {"dag": DAG_ID, "status": "published"}

    precheck = precheck_inputs()
    validated = validate_stg(precheck)
    published = publish_signal()
    precheck >> spark_job >> validated >> published


dag = spark_preprocess_to_stg()
