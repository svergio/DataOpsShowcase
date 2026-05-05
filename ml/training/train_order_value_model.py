from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

import boto3
import mlflow
import mlflow.spark
from pyspark.ml import Pipeline
from pyspark.ml.evaluation import RegressionEvaluator
from pyspark.ml.feature import StringIndexer, VectorAssembler
from pyspark.ml.regression import GBTRegressor
from pyspark.sql import functions as F

from lib_runtime import jdbc_props
from spark_session import build_spark_session


DEFAULT_BUCKET = "mlflow-artifacts"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execution-ts", required=True)
    parser.add_argument("--env", default=os.environ.get("SPARK_JOB_ENV", "production"))
    parser.add_argument("--jdbc-url", default=os.environ.get("DWH_JDBC_URL"))
    parser.add_argument("--jdbc-user", default=os.environ.get("DWH_JDBC_USER"))
    parser.add_argument("--jdbc-password", default=os.environ.get("DWH_JDBC_PASSWORD"))
    parser.add_argument("--lookback-days", type=int, default=30)
    parser.add_argument("--train-ratio", type=float, default=0.8)
    return parser.parse_args()


def ensure_bucket(endpoint_url: str, access_key: str, secret_key: str, bucket_name: str) -> None:
    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
    )
    existing = {b["Name"] for b in s3.list_buckets().get("Buckets", [])}
    if bucket_name not in existing:
        s3.create_bucket(Bucket=bucket_name)


def main() -> int:
    args = parse_args()
    if not (args.jdbc_url and args.jdbc_user and args.jdbc_password):
        print("[FAIL] DWH JDBC credentials are missing", file=sys.stderr)
        return 1

    mlflow_tracking_uri = os.environ.get("MLFLOW_TRACKING_URI", "http://mlflow:5000")
    mlflow_experiment_name = os.environ.get("MLFLOW_EXPERIMENT_NAME", "DataOpsShowcaseSpark")
    mlflow_model_name = os.environ.get("MLFLOW_MODEL_NAME", "orders_revenue_regressor")
    mlflow_s3_endpoint = os.environ.get("MLFLOW_S3_ENDPOINT_URL", "http://minio:9000")
    aws_access_key = os.environ.get("AWS_ACCESS_KEY_ID", "minio")
    aws_secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY", "minio123")

    artifact_root = os.environ.get("MLFLOW_ARTIFACT_ROOT", f"s3://{DEFAULT_BUCKET}")
    artifact_uri = artifact_root[5:] if artifact_root.startswith("s3://") else artifact_root
    artifact_bucket = artifact_uri.split("/", 1)[0] or DEFAULT_BUCKET
    ensure_bucket(mlflow_s3_endpoint, aws_access_key, aws_secret_key, artifact_bucket)

    spark = build_spark_session("dataops_train_order_value_model")

    mlflow.set_tracking_uri(mlflow_tracking_uri)
    mlflow.set_experiment(mlflow_experiment_name)
    # Use explicit logging instead of Spark autolog JAR hooks for portability.

    cutoff_expr = F.current_timestamp() - F.expr(f"INTERVAL {int(args.lookback_days)} DAYS")
    props = jdbc_props(args.jdbc_user, args.jdbc_password)

    try:
        try:
            orders = spark.read.jdbc(args.jdbc_url, "dwh_staging.stg_orders", properties=props).select(
                "status",
                "currency",
                "customer_bk",
                "order_ts",
                "total_amount",
            )
        except Exception:
            try:
                orders = spark.read.jdbc(args.jdbc_url, "staging.stg_orders", properties=props).select(
                    F.col("status"),
                    F.col("currency_code").alias("currency"),
                    F.col("customer_id").cast("string").alias("customer_bk"),
                    F.col("order_ts"),
                    F.col("total_amount"),
                )
            except Exception as exc:
                raise RuntimeError(
                    "ML training requires anonymized staging.stg_orders (or dwh_staging.stg_orders); raw OLTP is not used."
                ) from exc
        training_df = (
            orders.select("status", "currency", "customer_bk", "order_ts", "total_amount")
            .where(F.col("order_ts").isNotNull() & F.col("total_amount").isNotNull())
            .where(F.col("order_ts") >= cutoff_expr)
            .withColumn("order_hour", F.hour("order_ts"))
            .withColumn("order_dayofweek", F.dayofweek("order_ts"))
            .withColumn("label", F.col("total_amount").cast("double"))
            .where(F.col("label") > 0)
        )

        row_count = training_df.count()
        if row_count < 50:
            raise ValueError(f"Not enough training data: {row_count} rows")

        train_df, test_df = training_df.randomSplit([args.train_ratio, 1 - args.train_ratio], seed=42)

        status_indexer = StringIndexer(
            inputCol="status", outputCol="status_idx", handleInvalid="keep"
        )
        currency_indexer = StringIndexer(
            inputCol="currency", outputCol="currency_idx", handleInvalid="keep"
        )
        customer_indexer = StringIndexer(
            inputCol="customer_bk", outputCol="customer_idx", handleInvalid="keep"
        )
        assembler = VectorAssembler(
            inputCols=["status_idx", "currency_idx", "customer_idx", "order_hour", "order_dayofweek"],
            outputCol="features",
        )
        regressor = GBTRegressor(
            featuresCol="features",
            labelCol="label",
            predictionCol="prediction",
            maxIter=40,
            maxDepth=5,
            stepSize=0.1,
            seed=42,
        )

        pipeline = Pipeline(stages=[status_indexer, currency_indexer, customer_indexer, assembler, regressor])

        with mlflow.start_run(run_name=f"train_order_value_{args.execution_ts}") as run:
            model = pipeline.fit(train_df)
            pred_df = model.transform(test_df).cache()
            rmse = RegressionEvaluator(
                labelCol="label", predictionCol="prediction", metricName="rmse"
            ).evaluate(pred_df)
            mae = RegressionEvaluator(
                labelCol="label", predictionCol="prediction", metricName="mae"
            ).evaluate(pred_df)
            r2 = RegressionEvaluator(
                labelCol="label", predictionCol="prediction", metricName="r2"
            ).evaluate(pred_df)

            mlflow.log_param("lookback_days", args.lookback_days)
            mlflow.log_param("train_ratio", args.train_ratio)
            mlflow.log_param("train_rows", train_df.count())
            mlflow.log_param("test_rows", test_df.count())
            mlflow.log_metric("rmse", rmse)
            mlflow.log_metric("mae", mae)
            mlflow.log_metric("r2", r2)

            mlflow.spark.log_model(
                spark_model=model,
                artifact_path="model",
                registered_model_name=mlflow_model_name,
            )

            print(
                "[OK] ml training finished",
                f"run_id={run.info.run_id}",
                f"rmse={rmse:.4f}",
                f"mae={mae:.4f}",
                f"r2={r2:.4f}",
            )
        return 0
    finally:
        spark.stop()


if __name__ == "__main__":
    sys.exit(main())
