#!/usr/bin/env python3
"""
Kafka (Debezium JSON payload in value) -> Spark Structured Streaming console sink (demo).

Submit example (from spark_master container):

  /opt/spark/bin/spark-submit \\
    --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1 \\
    /opt/spark/jobs/cdc_structured_stream.py \\
    --bootstrap-servers kafka:9092 --subscribe-pattern 'cdc_.*' --starting-offsets latest

foreachBatch (OLAP / Delta / JDBC): in production, replace the console sink with:

  def upsert_batch(df, batch_id): ...
  query = parsed.writeStream.foreachBatch(upsert_batch).option("checkpointLocation", ...)
For JDBC you need a matching driver JAR on the Spark classpath (e.g. --jars postgresql.jar).
Schema Registry + Avro: add --packages org.apache.spark:spark-avro_2.12:3.5.1,
org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1 plus Confluent serializer settings.
"""
from __future__ import annotations

import argparse

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, expr


def foreach_batch_console_preview(df, batch_id: int) -> None:
    df.show(20, truncate=False)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--bootstrap-servers", default="kafka:9092")
    p.add_argument("--subscribe-pattern", default="cdc_.*")
    p.add_argument("--starting-offsets", default="latest", choices=("earliest", "latest"))
    p.add_argument("--checkpoint", default="/tmp/spark_cdc_ckpt")
    p.add_argument(
        "--sink",
        default="console",
        choices=("console", "foreach_preview"),
        help="console: writeStream to console; foreach_preview: demonstrates foreachBatch pattern",
    )
    args = p.parse_args()

    spark = (
        SparkSession.builder.appName("dataops_showcase.cdc_structured_stream")
        .master("local[*]")
        .getOrCreate()
    )

    raw = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", args.bootstrap_servers)
        .option("subscribePattern", args.subscribe_pattern)
        .option("startingOffsets", args.starting_offsets)
        .option("failOnDataLoss", "false")
        .load()
    )

    parsed = raw.select(
        col("topic"),
        col("partition"),
        col("offset"),
        col("timestamp"),
        expr("CAST(value AS STRING)").alias("value_json"),
    )

    if args.sink == "console":
        query = parsed.writeStream.option("checkpointLocation", args.checkpoint).outputMode("append").format("console").start()
    else:
        query = (
            parsed.writeStream.option("checkpointLocation", args.checkpoint)
            .outputMode("append")
            .foreachBatch(foreach_batch_console_preview)
            .start()
        )

    query.awaitTermination()


if __name__ == "__main__":
    main()
