from __future__ import annotations

import os
from datetime import datetime, timezone

from airflow.decorators import dag, task

from pipelines.utils.dag_factory import default_args
from pipelines.utils.datasets import DS_SERVING_OPTIMIZED, DS_SPARK_ANALYTICS_DONE
from pipelines.utils.spark_submit_factory import build_spark_submit_operator

DAG_ID = "dag_spark_analytics_to_marts"
SOURCE = "spark.analytics"


@dag(
    dag_id=DAG_ID,
    description="Spark serving analytics: write MinIO parquet + dwh_marts.spark_analytics",
    schedule=[DS_SERVING_OPTIMIZED],
    start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    default_args=default_args(),
    tags=["transformation", "spark", "serving", "analytics"],
)
def spark_analytics_to_marts() -> None:
    spark_job = build_spark_submit_operator(
        job_id="analytics_summary",
        task_id="spark_analytics_summary",
        application_args=[
            "--execution-ts",
            "{{ (data_interval_end or logical_date).isoformat() }}",
            "--minio-bucket",
            "{{ var.value.get('MINIO_BUCKET_RAW', 'raw') }}",
            "--minio-prefix",
            "{{ var.value.get('MINIO_PREFIX_SPARK_ANALYTICS', 'spark_analytics') }}",
        ],
        env_vars={
            "DWH_JDBC_URL": os.environ.get("DWH_JDBC_URL", "jdbc:postgresql://postgres_olap:5432/techmart_dwh"),
            "DWH_JDBC_USER": "{{ var.value.get('DWH_JDBC_USER', 'olap_user') }}",
            "DWH_JDBC_PASSWORD": "{{ var.value.get('DWH_JDBC_PASSWORD', 'olap_pass') }}",
            "AWS_ACCESS_KEY_ID": "{{ var.value.get('MINIO_ROOT_USER', 'minio') }}",
            "AWS_SECRET_ACCESS_KEY": "{{ var.value.get('MINIO_ROOT_PASSWORD', 'minio123') }}",
            "AWS_DEFAULT_REGION": os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
            "MINIO_ENDPOINT": os.environ.get("MINIO_ENDPOINT", "minio:9000"),
            "MINIO_BUCKET_RAW": os.environ.get("MINIO_BUCKET_RAW", "raw"),
            "MINIO_PREFIX_SPARK_ANALYTICS": os.environ.get("MINIO_PREFIX_SPARK_ANALYTICS", "spark_analytics"),
        },
        conf={
            "spark.jars.packages": "org.postgresql:postgresql:42.7.3,org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk-bundle:1.12.262",
            "spark.hadoop.fs.s3a.endpoint": "http://minio:9000",
            "spark.hadoop.fs.s3a.path.style.access": "true",
            "spark.hadoop.fs.s3a.impl": "org.apache.hadoop.fs.s3a.S3AFileSystem",
            "spark.hadoop.fs.s3a.connection.ssl.enabled": "false",
        },
        inlets=[DS_SERVING_OPTIMIZED],
    )

    @task(outlets=[DS_SPARK_ANALYTICS_DONE])
    def publish_signal() -> dict:
        return {"dag": DAG_ID, "status": "published"}

    spark_job >> publish_signal()


dag = spark_analytics_to_marts()
