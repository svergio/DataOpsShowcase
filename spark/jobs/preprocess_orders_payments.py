"""
Production Spark job for cleaning, deduplicating, schema-enforcing
and de-anonymizing raw events landed by ingestion DAGs.

Run: spark-submit --py-files lib_runtime.py,spark_session.py preprocess_orders_payments.py --execution-ts ...

Idempotency contract:
  - The job is bounded to a deterministic slice [ts_lower, ts_upper] derived
    from --execution-ts and --lookback-hours; same input slice produces the
    same logical result for any number of re-runs.
  - Writes are upserts (INSERT ... ON CONFLICT) into staging.stg_*; no full
    table overwrite of staging tables is performed.
  - A per-slice scratch table (staging._stage_<target>_<slug>) is used as
    deterministic landing spot for the JDBC writer and is dropped at end.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

from pyspark.sql import DataFrame, SparkSession, Window
from pyspark.sql import functions as F
from pyspark.sql.types import TimestampType

from lib_runtime import JDBC_DRIVER, execution_slug, jdbc_props, parse_execution_ts, safe_table_token
from spark_session import build_spark_session


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execution-ts", required=True)
    parser.add_argument("--lookback-hours", type=int, default=2)
    parser.add_argument("--jdbc-url", default=os.environ.get("DWH_JDBC_URL"))
    parser.add_argument("--jdbc-user", default=os.environ.get("DWH_JDBC_USER"))
    parser.add_argument("--jdbc-password", default=os.environ.get("DWH_JDBC_PASSWORD"))
    return parser.parse_args()


def _exec_jdbc_sql(spark: SparkSession, jdbc_url: str, props: dict[str, str], sql: str) -> None:
    jvm = spark._jvm  # type: ignore[attr-defined]
    jvm.java.lang.Class.forName(JDBC_DRIVER)
    conn = jvm.java.sql.DriverManager.getConnection(jdbc_url, props["user"], props["password"])
    try:
        stmt = conn.createStatement()
        try:
            stmt.execute(sql)
        finally:
            stmt.close()
    finally:
        conn.close()


def _read_table(spark: SparkSession, jdbc_url: str, table: str, props: dict[str, str]) -> DataFrame:
    return spark.read.jdbc(jdbc_url, table, properties=props)


def _hash_columns(df: DataFrame, columns: list[str], alias: str) -> DataFrame:
    expr = F.sha2(
        F.concat_ws("||", *[F.coalesce(F.col(c).cast("string"), F.lit("")) for c in columns]),
        256,
    )
    return df.withColumn(alias, expr)


def _slice_filter(df: DataFrame, ts_lower: datetime, ts_upper: datetime) -> DataFrame:
    return df.filter(
        (F.col("ingested_at") >= F.lit(ts_lower)) & (F.col("ingested_at") <= F.lit(ts_upper))
    )


def _write_incremental_upsert(
    spark: SparkSession,
    df: DataFrame,
    jdbc_url: str,
    target_table: str,
    *,
    pk_columns: list[str],
    update_columns: list[str],
    props: dict[str, str],
    execution_slug: str,
) -> int:
    if df.limit(1).count() == 0:
        return 0

    select_cols = pk_columns + update_columns
    staged = df.select(*select_cols)

    temp_table = f"staging._stage_{safe_table_token(target_table)}_{execution_slug}"

    _exec_jdbc_sql(spark, jdbc_url, props, f"DROP TABLE IF EXISTS {temp_table}")
    staged.write.jdbc(
        jdbc_url,
        temp_table,
        mode="overwrite",
        properties={**props, "truncate": "false"},
    )

    cols_sql = ", ".join(select_cols)
    pk_sql = ", ".join(pk_columns)
    if update_columns:
        update_sql = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_columns)
        upsert_sql = (
            f"INSERT INTO {target_table} ({cols_sql}) "
            f"SELECT {cols_sql} FROM {temp_table} "
            f"ON CONFLICT ({pk_sql}) DO UPDATE SET {update_sql}"
        )
    else:
        upsert_sql = (
            f"INSERT INTO {target_table} ({cols_sql}) "
            f"SELECT {cols_sql} FROM {temp_table} "
            f"ON CONFLICT ({pk_sql}) DO NOTHING"
        )

    _exec_jdbc_sql(spark, jdbc_url, props, upsert_sql)
    _exec_jdbc_sql(spark, jdbc_url, props, f"DROP TABLE IF EXISTS {temp_table}")

    return staged.count()


def deanonymize_users(spark: SparkSession, df: DataFrame, jdbc_url: str, props: dict[str, str]) -> DataFrame:
    users = _read_table(spark, jdbc_url, "raw.oltp_users", props).select(
        F.col("user_id").cast("long").alias("real_user_id"),
        F.col("email").alias("email_real"),
        F.col("full_name").alias("full_name_real"),
        F.col("created_at").alias("registered_at"),
    )
    deduped = users.withColumn(
        "row_num",
        F.row_number().over(
            Window.partitionBy("real_user_id").orderBy(F.col("registered_at").desc_nulls_last())
        ),
    ).filter("row_num = 1").drop("row_num")
    return df.join(deduped, df.customer_id == deduped.real_user_id, how="left")


def build_stg_customers(
    spark: SparkSession,
    jdbc_url: str,
    props: dict[str, str],
    ts_lower: datetime,
    ts_upper: datetime,
) -> DataFrame:
    users = _read_table(spark, jdbc_url, "raw.oltp_users", props)
    sliced = _slice_filter(users, ts_lower, ts_upper)
    schema_check = sliced.filter(F.col("user_id").isNotNull() & F.col("email").isNotNull())
    deduped = schema_check.withColumn(
        "row_num",
        F.row_number().over(
            Window.partitionBy("user_id").orderBy(F.col("ingested_at").desc_nulls_last())
        ),
    ).filter("row_num = 1").drop("row_num")
    cleaned = deduped.select(
        F.col("user_id").cast("long").alias("customer_id"),
        F.lower(F.trim(F.col("email"))).alias("email"),
        F.trim(F.col("full_name")).alias("full_name"),
        F.col("created_at").cast(TimestampType()).alias("registered_at"),
    )
    return _hash_columns(cleaned, ["customer_id", "email", "full_name"], "source_record_hash")


def build_stg_orders(
    spark: SparkSession,
    jdbc_url: str,
    props: dict[str, str],
    ts_lower: datetime,
    ts_upper: datetime,
) -> DataFrame:
    raw = _read_table(spark, jdbc_url, "raw.oltp_orders", props)
    sliced = _slice_filter(raw, ts_lower, ts_upper)
    deduped = sliced.withColumn(
        "row_num",
        F.row_number().over(
            Window.partitionBy("order_id").orderBy(F.col("ingested_at").desc_nulls_last())
        ),
    ).filter("row_num = 1").drop("row_num")
    cleaned = (
        deduped.filter(
            F.col("order_id").isNotNull()
            & F.col("user_id").isNotNull()
            & F.col("order_ts").isNotNull()
            & (F.col("total_amount") >= 0)
        )
        .select(
            F.col("order_id").cast("long"),
            F.col("user_id").cast("long").alias("customer_id"),
            F.col("order_ts").cast(TimestampType()),
            F.lower(F.trim(F.col("status"))).alias("status"),
            F.upper(F.col("currency_code")).alias("currency_code"),
            F.col("total_amount").cast("decimal(14,2)"),
        )
    )
    return _hash_columns(
        cleaned,
        ["order_id", "customer_id", "status", "currency_code", "total_amount"],
        "source_record_hash",
    )


def build_stg_order_events(
    spark: SparkSession,
    jdbc_url: str,
    props: dict[str, str],
    ts_lower: datetime,
    ts_upper: datetime,
) -> DataFrame:
    raw = _read_table(spark, jdbc_url, "raw.kafka_orders", props)
    sliced = _slice_filter(raw, ts_lower, ts_upper)
    deduped = sliced.withColumn(
        "row_num",
        F.row_number().over(
            Window.partitionBy("topic", "partition_id", "kafka_offset").orderBy(
                F.col("ingested_at").desc_nulls_last()
            )
        ),
    ).filter("row_num = 1").drop("row_num")
    deanon = deanonymize_users(spark, deduped, jdbc_url, props)
    return deanon.filter(F.col("event_id").isNotNull()).select(
        F.concat_ws(":", F.col("topic"), F.col("partition_id"), F.col("kafka_offset")).alias("event_uuid"),
        F.col("event_id"),
        F.col("event_type"),
        F.col("order_id").cast("long"),
        F.coalesce(F.col("real_user_id"), F.col("customer_id")).cast("long").alias("customer_id"),
        F.col("total_amount").cast("decimal(14,2)"),
        F.upper(F.col("currency")).alias("currency"),
        F.upper(F.col("country_code")).alias("country_code"),
        F.col("event_ts").cast(TimestampType()),
    )


def build_stg_payment_events(
    spark: SparkSession,
    jdbc_url: str,
    props: dict[str, str],
    ts_lower: datetime,
    ts_upper: datetime,
) -> DataFrame:
    raw = _read_table(spark, jdbc_url, "raw.kafka_payments", props)
    sliced = _slice_filter(raw, ts_lower, ts_upper)
    deduped = sliced.withColumn(
        "row_num",
        F.row_number().over(
            Window.partitionBy("topic", "partition_id", "kafka_offset").orderBy(
                F.col("ingested_at").desc_nulls_last()
            )
        ),
    ).filter("row_num = 1").drop("row_num")
    return deduped.filter(F.col("event_id").isNotNull()).select(
        F.concat_ws(":", F.col("topic"), F.col("partition_id"), F.col("kafka_offset")).alias("event_uuid"),
        F.col("event_id"),
        F.col("event_type"),
        F.col("payment_id").cast("long"),
        F.col("order_id").cast("long"),
        F.col("transaction_id"),
        F.col("amount").cast("decimal(14,2)"),
        F.upper(F.col("currency")).alias("currency"),
        F.lower(F.col("payment_method")).alias("payment_method"),
        F.lower(F.col("status")).alias("status"),
        F.col("decline_reason"),
        F.col("event_ts").cast(TimestampType()),
    )


def main() -> int:
    args = _parse_args()
    if not (args.jdbc_url and args.jdbc_user and args.jdbc_password):
        print("[FAIL] DWH JDBC credentials are missing", file=sys.stderr)
        return 1

    exec_dt = parse_execution_ts(args.execution_ts)
    ts_upper = exec_dt
    ts_lower = exec_dt - timedelta(hours=int(args.lookback_hours))
    slug = execution_slug(exec_dt)

    spark = build_spark_session("dataops_preprocess_orders_payments")
    props = jdbc_props(args.jdbc_user, args.jdbc_password)
    try:
        _exec_jdbc_sql(spark, args.jdbc_url, props, "CREATE SCHEMA IF NOT EXISTS staging")

        stg_customers = build_stg_customers(spark, args.jdbc_url, props, ts_lower, ts_upper)
        stg_orders = build_stg_orders(spark, args.jdbc_url, props, ts_lower, ts_upper)
        stg_order_events = build_stg_order_events(spark, args.jdbc_url, props, ts_lower, ts_upper)
        stg_payment_events = build_stg_payment_events(spark, args.jdbc_url, props, ts_lower, ts_upper)

        n_customers = _write_incremental_upsert(
            spark, stg_customers, args.jdbc_url, "staging.stg_customers",
            pk_columns=["customer_id"],
            update_columns=["email", "full_name", "registered_at", "source_record_hash"],
            props=props, execution_slug=slug,
        )
        n_orders = _write_incremental_upsert(
            spark, stg_orders, args.jdbc_url, "staging.stg_orders",
            pk_columns=["order_id"],
            update_columns=[
                "customer_id", "order_ts", "status", "currency_code",
                "total_amount", "source_record_hash",
            ],
            props=props, execution_slug=slug,
        )
        n_order_events = _write_incremental_upsert(
            spark, stg_order_events, args.jdbc_url, "staging.stg_order_events",
            pk_columns=["event_uuid"],
            update_columns=[
                "event_id", "event_type", "order_id", "customer_id",
                "total_amount", "currency", "country_code", "event_ts",
            ],
            props=props, execution_slug=slug,
        )
        n_payment_events = _write_incremental_upsert(
            spark, stg_payment_events, args.jdbc_url, "staging.stg_payment_events",
            pk_columns=["event_uuid"],
            update_columns=[
                "event_id", "event_type", "payment_id", "order_id", "transaction_id",
                "amount", "currency", "payment_method", "status", "decline_reason",
                "event_ts",
            ],
            props=props, execution_slug=slug,
        )

        print(
            "[OK] preprocessing finished",
            f"execution_ts={args.execution_ts}",
            f"slice_lower={ts_lower.isoformat()}",
            f"slice_upper={ts_upper.isoformat()}",
            f"customers={n_customers}",
            f"orders={n_orders}",
            f"order_events={n_order_events}",
            f"payment_events={n_payment_events}",
        )
        return 0
    finally:
        spark.stop()


if __name__ == "__main__":
    sys.exit(main())
