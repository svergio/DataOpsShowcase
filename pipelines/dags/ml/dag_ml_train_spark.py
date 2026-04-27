from __future__ import annotations

import os
from datetime import datetime, timezone

from airflow.decorators import dag, task
from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator

from pipelines.utils.dag_factory import default_args
from pipelines.utils.datasets import DS_DBT_MARTS_DONE, DS_ML_TRAIN_DONE


DAG_ID = "dag_ml_train_spark"
SOURCE = "spark.ml.training"
SPARK_APPLICATION = "/opt/airflow/ml/training/train_order_value_model.py"
SPARK_PY_FILES = (
    "/opt/airflow/spark/common/lib_runtime.py,"
    "/opt/airflow/spark/common/spark_session.py"
)


@dag(
    dag_id=DAG_ID,
    description="Spark ML training with MLflow tracking and model registry",
    schedule=[DS_DBT_MARTS_DONE],
    start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    default_args=default_args({"retries": 2}),
    tags=["ml", "spark", "mlflow"],
)
def ml_train_spark() -> None:
    @task
    def precheck() -> dict:
        from services.common.logging_utils import get_logger
        from services.common.run_metadata import finish_run, start_run
        from services.storage.postgres_io import fetch_one

        run_meta = start_run(
            dag_id=DAG_ID,
            task_id="precheck",
            source=SOURCE,
            layer="mlops",
        )
        try:
            row = fetch_one(
                "postgres_dwh",
                """
                WITH cnt AS (
                    SELECT CASE
                        WHEN to_regclass('dwh_staging.stg_orders') IS NOT NULL
                        THEN (SELECT COUNT(*)::bigint FROM dwh_staging.stg_orders)
                        ELSE 0::bigint
                    END AS dwh_cnt,
                    CASE
                        WHEN to_regclass('staging.stg_orders') IS NOT NULL
                        THEN (SELECT COUNT(*)::bigint FROM staging.stg_orders)
                        ELSE 0::bigint
                    END AS stg_cnt
                    ,
                    CASE
                        WHEN to_regclass('raw.oltp_orders') IS NOT NULL
                        THEN (SELECT COUNT(*)::bigint FROM raw.oltp_orders)
                        ELSE 0::bigint
                    END AS raw_cnt
                )
                SELECT dwh_cnt + stg_cnt + raw_cnt FROM cnt
                """,
            )
            stg_orders_cnt = int(row[0]) if row else 0
            if stg_orders_cnt == 0:
                raise ValueError("No rows in dwh_staging.stg_orders, staging.stg_orders, raw.oltp_orders")
            payload = {"stg_orders_count": stg_orders_cnt}
            get_logger(DAG_ID).info("ml precheck passed", extra={"extra_payload": payload})
            finish_run(run_meta, status="success", rows_in=stg_orders_cnt, payload=payload)
            return payload
        except Exception as exc:
            finish_run(run_meta, status="failed", error_message=str(exc))
            raise

    train = SparkSubmitOperator(
        task_id="spark_train_model",
        application=SPARK_APPLICATION,
        py_files=SPARK_PY_FILES,
        conn_id="spark_default",
        name="dataops_ml_train_order_value",
        application_args=[
            "--execution-ts",
            "{{ data_interval_end | default(ts) }}",
            "--lookback-days",
            "60",
            "--train-ratio",
            "0.8",
        ],
        env_vars={
            "DWH_JDBC_URL": os.environ.get(
                "DWH_JDBC_URL",
                "jdbc:postgresql://postgres_olap:5432/techmart_dwh",
            ),
            "DWH_JDBC_USER": os.environ.get("DWH_JDBC_USER", "olap_user"),
            "DWH_JDBC_PASSWORD": os.environ.get("DWH_JDBC_PASSWORD", "olap_pass"),
            "MLFLOW_TRACKING_URI": os.environ.get("MLFLOW_TRACKING_URI", "http://mlflow:5000"),
            "MLFLOW_EXPERIMENT_NAME": os.environ.get("MLFLOW_EXPERIMENT_NAME", "DataOpsShowcaseSpark"),
            "MLFLOW_MODEL_NAME": os.environ.get("MLFLOW_MODEL_NAME", "orders_revenue_regressor"),
            "MLFLOW_S3_ENDPOINT_URL": os.environ.get("MLFLOW_S3_ENDPOINT_URL", "http://minio:9000"),
            "MLFLOW_ARTIFACT_ROOT": os.environ.get("MLFLOW_ARTIFACT_ROOT", "s3://mlflow-artifacts"),
            "AWS_ACCESS_KEY_ID": os.environ.get("MINIO_ROOT_USER", "minio"),
            "AWS_SECRET_ACCESS_KEY": os.environ.get("MINIO_ROOT_PASSWORD", "minio123"),
            "AWS_DEFAULT_REGION": os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
        },
        conf={
            "spark.jars.packages": "org.postgresql:postgresql:42.7.3",
            "spark.executorEnv.MLFLOW_TRACKING_URI": os.environ.get("MLFLOW_TRACKING_URI", "http://mlflow:5000"),
            "spark.executorEnv.MLFLOW_S3_ENDPOINT_URL": os.environ.get("MLFLOW_S3_ENDPOINT_URL", "http://minio:9000"),
            "spark.executorEnv.AWS_ACCESS_KEY_ID": os.environ.get("MINIO_ROOT_USER", "minio"),
            "spark.executorEnv.AWS_SECRET_ACCESS_KEY": os.environ.get("MINIO_ROOT_PASSWORD", "minio123"),
            "spark.executorEnv.AWS_DEFAULT_REGION": os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
        },
        retries=2,
        executor_cores=2,
        executor_memory="2g",
        driver_memory="2g",
        num_executors=1,
    )

    @task(outlets=[DS_ML_TRAIN_DONE])
    def publish_signal() -> dict:
        from services.common.logging_utils import get_logger

        payload = {"dag": DAG_ID, "status": "published"}
        get_logger(DAG_ID).info("ml train signal", extra={"extra_payload": payload})
        return payload

    precheck() >> train >> publish_signal()


dag = ml_train_spark()
