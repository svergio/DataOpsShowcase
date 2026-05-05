from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from airflow.decorators import dag, task

from pipelines.utils.airflow_callbacks import task_failure_callback, task_success_callback
from pipelines.utils.dag_factory import default_args
from pipelines.utils.datasets import DS_STG_CLEAN
from pipelines.utils.spark_schedule import raw_four_tuple, spark_preprocess_schedule
from pipelines.utils.spark_submit_factory import build_spark_submit_operator

DAG_ID = "dag_spark_preprocess_to_stg"
SOURCE = "spark.preprocess"

DAG_DOC = """
### Spark: raw to anonymized staging

**Privacy:** `staging.stg_*` has **no open PII** (no raw email, full name, phone). Salt: env `SPARK_PRIVACY_SALT` (required for `SPARK_JOB_ENV=production`).

**Schedule:** Airflow Variable `spark_preprocess_mode`:
- `all_raw` (default): **AND** on all four raw datasets (OLTP, Kafka orders/payments, MinIO).
- `any_raw`: **OR** (dev/testing; incomplete slices possible — see precheck/validate logs).

Runbook: `docs/runbook/AIRFLOW_DAG_TROUBLESHOOTING.md` in the repo.
"""


@dag(
    dag_id=DAG_ID,
    description="Spark preprocessing: raw -> staging with anonymization (hash + masked fields)",
    schedule=spark_preprocess_schedule(),
    start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    default_args=default_args(),
    tags=["transformation", "spark", "preprocessing", "privacy"],
    doc_md=DAG_DOC,
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

    raw_datasets = list(raw_four_tuple())
    spark_job = build_spark_submit_operator(
        job_id="preprocess_orders_payments",
        task_id="spark_preprocess",
        application_args=[
            "--execution-ts",
            "{{ (data_interval_end or logical_date).isoformat() }}",
            "--lookback-hours",
            "{{ var.value.get('SPARK_PREPROCESS_LOOKBACK_HOURS', 2) }}",
            "--env",
            "{{ var.value.get('SPARK_JOB_ENV', 'production') }}",
        ],
        env_vars={
            "DWH_JDBC_URL": os.environ.get(
                "DWH_JDBC_URL",
                "jdbc:postgresql://postgres_olap:5432/techmart_dwh",
            ),
            "DWH_JDBC_USER": "{{ var.value.get('DWH_JDBC_USER', 'olap_user') }}",
            "DWH_JDBC_PASSWORD": "{{ var.value.get('DWH_JDBC_PASSWORD', 'olap_pass') }}",
        },
        on_failure_callback=task_failure_callback,
        on_success_callback=task_success_callback,
        inlets=raw_datasets,
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
