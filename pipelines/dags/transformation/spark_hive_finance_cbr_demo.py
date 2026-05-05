from __future__ import annotations

import os
from datetime import datetime, timezone

from airflow.decorators import dag, task

from pipelines.utils.dag_factory import default_args
from pipelines.utils.datasets import DS_DBT_MARTS_DONE, DS_SPARK_HIVE_FINANCE_DONE
from pipelines.utils.spark_submit_factory import build_spark_submit_operator

DAG_ID = "dag_spark_hive_finance_cbr_demo"


@dag(
    dag_id=DAG_ID,
    description="Spark: CBR FX + dwh_marts (JDBC) -> demo_fin in postgres_olap (Superset finance demo)",
    schedule=[DS_DBT_MARTS_DONE],
    start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    default_args=default_args(),
    tags=["transformation", "spark", "postgres", "finance", "demo"],
)
def spark_hive_finance_cbr_demo() -> None:
    spark_job = build_spark_submit_operator(
        job_id="pg_finance_cbr_demo",
        task_id="spark_hive_finance_cbr_demo",
        application_args=[
            "--execution-ts",
            "{{ (data_interval_end or logical_date).isoformat() }}",
            "--lookback-days",
            "{{ var.value.get('SPARK_PG_FINANCE_LOOKBACK_DAYS', var.value.get('SPARK_HIVE_FINANCE_LOOKBACK_DAYS', '400')) }}",
        ],
        env_vars={
            "DWH_JDBC_URL": os.environ.get("DWH_JDBC_URL", "jdbc:postgresql://postgres_olap:5432/techmart_dwh"),
            "DWH_JDBC_USER": "{{ var.value.get('DWH_JDBC_USER', 'olap_user') }}",
            "DWH_JDBC_PASSWORD": "{{ var.value.get('DWH_JDBC_PASSWORD', 'olap_pass') }}",
        },
        conf={
            "spark.jars.packages": "org.postgresql:postgresql:42.7.3",
        },
        inlets=[DS_DBT_MARTS_DONE],
    )

    @task(outlets=[DS_SPARK_HIVE_FINANCE_DONE])
    def publish_signal() -> dict:
        return {"dag": DAG_ID, "status": "published"}

    spark_job >> publish_signal()


dag = spark_hive_finance_cbr_demo()
