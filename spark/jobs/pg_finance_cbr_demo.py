from __future__ import annotations

import argparse
import logging
import os
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, timedelta, timezone

from pyspark.sql import functions as F
from pyspark.sql.types import DateType, DoubleType, StringType, StructField, StructType

from lib_runtime import jdbc_props, parse_execution_ts
from spark_session import build_spark_session

logger = logging.getLogger(__name__)

CBR_SOAP_URL = "https://www.cbr.ru/DailyInfoWebServ/DailyInfo.asmx"

DEMO_SCHEMA = "demo_fin"


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--execution-ts", required=True)
    p.add_argument("--jdbc-url", default=os.environ.get("DWH_JDBC_URL"))
    p.add_argument("--jdbc-user", default=os.environ.get("DWH_JDBC_USER"))
    p.add_argument("--jdbc-password", default=os.environ.get("DWH_JDBC_PASSWORD"))
    p.add_argument("--lookback-days", type=int, default=400)
    p.add_argument("--cbr-timeout-sec", type=int, default=45)
    return p.parse_args()


def _ensure_demo_schema(spark, jdbc_url: str, user: str, password: str) -> None:
    jvm = spark.sparkContext._gateway.jvm
    conn = jvm.java.sql.DriverManager.getConnection(jdbc_url, user, password)
    try:
        st = conn.createStatement()
        try:
            st.executeUpdate(f"CREATE SCHEMA IF NOT EXISTS {DEMO_SCHEMA}")
        finally:
            st.close()
    finally:
        conn.close()


def _fetch_cbr_rates_on_date(on_date: date, timeout_sec: int) -> dict[str, float]:
    body = (
        '<?xml version="1.0" encoding="utf-8"?>'
        "<soap:Envelope xmlns:soap=\"http://schemas.xmlsoap.org/soap/envelope/\">"
        "<soap:Body><GetCursOnDateXML xmlns=\"http://web.cbr.ru/\">"
        f"<On_date>{on_date.isoformat()}</On_date>"
        "</GetCursOnDateXML></soap:Body></soap:Envelope>"
    )
    req = urllib.request.Request(
        CBR_SOAP_URL,
        data=body.encode("utf-8"),
        headers={
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": "http://web.cbr.ru/GetCursOnDateXML",
        },
        method="POST",
    )
    out: dict[str, float] = {"RUB": 1.0}
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        logger.warning("CBR SOAP failed for %s: %s", on_date, e)
        return out

    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        logger.warning("CBR XML parse failed for %s", on_date)
        return out

    for val in root.iter():
        if not val.tag.endswith("Valute"):
            continue
        code_el = val.find("CharCode")
        nominal_el = val.find("Nominal")
        value_el = val.find("Value")
        if code_el is None or nominal_el is None or value_el is None:
            continue
        code = (code_el.text or "").strip()
        try:
            nominal = float((nominal_el.text or "1").strip())
        except ValueError:
            nominal = 1.0
        val_txt = (value_el.text or "0").strip().replace(",", ".")
        try:
            rub_for_nominal = float(val_txt)
        except ValueError:
            continue
        if nominal <= 0:
            nominal = 1.0
        out[code] = rub_for_nominal / nominal
    return out


def _rates_rows_for_dates(dates: list[date], timeout_sec: int) -> list[tuple[date, str, float]]:
    rows: list[tuple[date, str, float]] = []
    seen: set[tuple[date, str]] = set()
    for d in sorted(set(dates)):
        rates = _fetch_cbr_rates_on_date(d, timeout_sec)
        for cur, rate in rates.items():
            key = (d, cur)
            if key in seen:
                continue
            seen.add(key)
            rows.append((d, cur, float(rate)))
    return rows


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = _parse_args()
    if not args.jdbc_url or not args.jdbc_user or not args.jdbc_password:
        raise RuntimeError("DWH_JDBC_URL / DWH_JDBC_USER / DWH_JDBC_PASSWORD are required")

    execution_ts = parse_execution_ts(args.execution_ts)
    run_id = execution_ts.astimezone(timezone.utc).strftime("%Y%m%d_%H%M%S")
    end_d = execution_ts.date()
    start_d = end_d - timedelta(days=max(1, args.lookback_days))

    spark = build_spark_session("dataops_pg_finance_cbr_demo")
    spark.sparkContext.setLogLevel("WARN")

    jdbc = jdbc_props(args.jdbc_user, args.jdbc_password)
    _ensure_demo_schema(spark, args.jdbc_url, args.jdbc_user, args.jdbc_password)

    daily = spark.read.jdbc(
        args.jdbc_url,
        "(SELECT order_date, currency, gross_sales, order_count, avg_order_value FROM dwh_marts.fct_daily_sales "
        f"WHERE order_date >= DATE '{start_d}' AND order_date <= DATE '{end_d}') AS q",
        properties=jdbc,
    )
    orders = spark.read.jdbc(
        args.jdbc_url,
        "(SELECT order_date, currency, payment_state, total_amount FROM dwh_marts.fct_orders "
        f"WHERE order_date >= DATE '{start_d}' AND order_date <= DATE '{end_d}') AS o",
        properties=jdbc,
    )

    dates_df = daily.select(F.col("order_date").cast("date").alias("d")).union(
        orders.select(F.col("order_date").cast("date").alias("d"))
    ).distinct()
    py_dates = [row.d for row in dates_df.collect() if row.d is not None]

    rate_tuples = _rates_rows_for_dates(py_dates or [end_d], args.cbr_timeout_sec)
    rate_schema = StructType(
        [
            StructField("rate_date", DateType(), False),
            StructField("currency", StringType(), False),
            StructField("rate_to_rub", DoubleType(), False),
        ]
    )
    rates_df = spark.createDataFrame(rate_tuples, schema=rate_schema)

    d1 = daily.withColumn("rate_date", F.col("order_date").cast("date"))
    joined = (
        d1.join(rates_df, on=["rate_date", "currency"], how="left")
        .withColumn("rate_to_rub", F.coalesce(F.col("rate_to_rub"), F.lit(1.0)))
        .withColumn("gross_sales_rub", F.col("gross_sales") * F.col("rate_to_rub"))
    )

    out_daily = joined.select(
        F.lit(run_id).alias("run_id"),
        F.col("order_date"),
        F.col("currency"),
        F.col("gross_sales").cast("double"),
        F.col("rate_to_rub").cast("double"),
        F.col("gross_sales_rub").cast("double"),
        F.col("order_count").cast("long"),
        F.col("avg_order_value").cast("double"),
    )

    o1 = orders.withColumn("rate_date", F.col("order_date").cast("date"))
    oj = (
        o1.join(rates_df, on=["rate_date", "currency"], how="left")
        .withColumn("rate_to_rub", F.coalesce(F.col("rate_to_rub"), F.lit(1.0)))
        .withColumn("amount_rub", F.col("total_amount") * F.col("rate_to_rub"))
    )
    mix = oj.groupBy("order_date", "currency", "payment_state").agg(
        F.count("*").alias("order_count"),
        F.sum("total_amount").cast("double").alias("revenue_orig"),
        F.sum("amount_rub").cast("double").alias("revenue_rub"),
    )
    out_mix = mix.select(
        F.lit(run_id).alias("run_id"),
        F.col("order_date"),
        F.col("currency"),
        F.col("payment_state"),
        F.col("order_count"),
        F.col("revenue_orig"),
        F.col("revenue_rub"),
    )

    daily_table = f"{DEMO_SCHEMA}.mart_daily_finance_rub"
    mix_table = f"{DEMO_SCHEMA}.mart_order_mix_rub"

    out_daily.write.mode("overwrite").option("truncate", "true").jdbc(
        args.jdbc_url,
        daily_table,
        properties=jdbc,
    )
    out_mix.write.mode("overwrite").option("truncate", "true").jdbc(
        args.jdbc_url,
        mix_table,
        properties=jdbc,
    )
    logger.info(
        "Postgres tables refreshed: %s, %s run_id=%s",
        daily_table,
        mix_table,
        run_id,
    )


if __name__ == "__main__":
    main()
