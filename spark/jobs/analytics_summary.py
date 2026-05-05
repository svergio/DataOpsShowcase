from __future__ import annotations

import argparse
import os

from pyspark.sql import functions as F

from lib_runtime import jdbc_props, parse_execution_ts
from spark_session import build_spark_session


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execution-ts", required=True)
    parser.add_argument("--jdbc-url", default=os.environ.get("DWH_JDBC_URL"))
    parser.add_argument("--jdbc-user", default=os.environ.get("DWH_JDBC_USER"))
    parser.add_argument("--jdbc-password", default=os.environ.get("DWH_JDBC_PASSWORD"))
    parser.add_argument("--minio-bucket", default=os.environ.get("MINIO_BUCKET_RAW", "raw"))
    parser.add_argument("--minio-prefix", default=os.environ.get("MINIO_PREFIX_SPARK_ANALYTICS", "spark_analytics"))
    return parser.parse_args()


def _exec_sql(spark, jdbc_url: str, user: str, password: str, sql: str) -> None:
    jvm = spark._jvm  # type: ignore[attr-defined]
    jvm.java.lang.Class.forName("org.postgresql.Driver")
    conn = jvm.java.sql.DriverManager.getConnection(jdbc_url, user, password)
    try:
        stmt = conn.createStatement()
        try:
            stmt.execute(sql)
        finally:
            stmt.close()
    finally:
        conn.close()


def main() -> None:
    args = _parse_args()
    if not args.jdbc_url or not args.jdbc_user or not args.jdbc_password:
        raise RuntimeError("DWH_JDBC_URL / DWH_JDBC_USER / DWH_JDBC_PASSWORD are required")

    execution_ts = parse_execution_ts(args.execution_ts)
    spark = build_spark_session("dataops_spark_analytics_summary")
    spark.sparkContext.setLogLevel("WARN")

    _exec_sql(
        spark,
        args.jdbc_url,
        args.jdbc_user,
        args.jdbc_password,
        """
        CREATE TABLE IF NOT EXISTS dwh_marts.spark_analytics (
          run_id TEXT NOT NULL,
          bucket_ts TIMESTAMPTZ NOT NULL,
          metric_name TEXT NOT NULL,
          dimension TEXT NOT NULL DEFAULT 'all',
          metric_value NUMERIC(18, 4) NOT NULL,
          extra_json JSONB NOT NULL DEFAULT '{}'::jsonb,
          loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (run_id, bucket_ts, metric_name, dimension)
        )
        """,
    )

    jdbc = jdbc_props(args.jdbc_user, args.jdbc_password)
    fct_orders = spark.read.jdbc(args.jdbc_url, "dwh_marts.fct_orders", properties=jdbc)
    fct_daily = spark.read.jdbc(args.jdbc_url, "dwh_marts.fct_daily_sales", properties=jdbc)
    dim_products = spark.read.jdbc(args.jdbc_url, "dwh_marts.dim_products", properties=jdbc)

    run_id = execution_ts.strftime("%Y%m%d_%H%M%S")
    bucket_ts_literal = F.lit(execution_ts.isoformat()).cast("timestamp")

    metrics_all = fct_orders.agg(
        F.count("*").cast("double").alias("orders_total"),
        F.sum("total_amount").cast("double").alias("orders_gross_sales"),
        F.avg("total_amount").cast("double").alias("avg_order_value"),
    ).select(
        F.lit(run_id).alias("run_id"),
        bucket_ts_literal.alias("bucket_ts"),
        F.expr("stack(3, 'orders_total', orders_total, 'orders_gross_sales', orders_gross_sales, 'avg_order_value', avg_order_value) as (metric_name, metric_value)"),
    ).withColumn("dimension", F.lit("all"))

    by_currency = fct_daily.groupBy("currency").agg(F.sum("gross_sales").cast("double").alias("metric_value")).select(
        F.lit(run_id).alias("run_id"),
        bucket_ts_literal.alias("bucket_ts"),
        F.lit("daily_sales_by_currency").alias("metric_name"),
        F.coalesce(F.col("currency"), F.lit("unknown")).alias("dimension"),
        F.col("metric_value"),
    )

    top_category = dim_products.groupBy("category").count().orderBy(F.col("count").desc()).limit(1).select(
        F.lit(run_id).alias("run_id"),
        bucket_ts_literal.alias("bucket_ts"),
        F.lit("top_product_category_count").alias("metric_name"),
        F.coalesce(F.col("category"), F.lit("unknown")).alias("dimension"),
        F.col("count").cast("double").alias("metric_value"),
    )

    result_df = metrics_all.unionByName(by_currency).unionByName(top_category).withColumn(
        "extra_json", F.lit("{}")
    ).withColumn("loaded_at", F.current_timestamp())

    s3a_path = f"s3a://{args.minio_bucket}/{args.minio_prefix}/run_id={run_id}"
    (
        result_df.coalesce(1)
        .write.mode("overwrite")
        .parquet(s3a_path)
    )

    (
        result_df.write.mode("append")
        .jdbc(
            url=args.jdbc_url,
            table="dwh_marts.spark_analytics",
            properties=jdbc,
        )
    )

    spark.stop()


if __name__ == "__main__":
    main()
