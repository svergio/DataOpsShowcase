from __future__ import annotations

import os

import pytest

pytest.importorskip("psycopg")


def _olap_dsn() -> str | None:
    return os.getenv("ETL_OLAP_DSN")


def _min_rows() -> int:
    raw = os.getenv("ETL_MIN_ROWS", "0").strip()
    return int(raw) if raw.isdigit() else 0


@pytest.mark.etl_raw
@pytest.mark.skipif(not _olap_dsn(), reason="ETL_OLAP_DSN not set (postgresql://... OLAP/DWH)")
def test_raw_layer_row_counts() -> None:
    import psycopg

    dsn = _olap_dsn()
    assert dsn
    min_n = _min_rows()
    with psycopg.connect(dsn, connect_timeout=15) as conn:
        with conn.cursor() as cur:
            for tbl in ("raw.kafka_orders", "raw.kafka_payments", "raw.oltp_orders"):
                cur.execute(f"SELECT count(*) FROM {tbl}")
                n = cur.fetchone()[0]
                assert n >= min_n, f"{tbl} count {n} < ETL_MIN_ROWS={min_n}"


@pytest.mark.etl_staging
@pytest.mark.skipif(not _olap_dsn(), reason="ETL_OLAP_DSN not set")
def test_staging_layer_row_counts() -> None:
    import psycopg

    dsn = _olap_dsn()
    assert dsn
    min_n = max(_min_rows(), 1)
    with psycopg.connect(dsn, connect_timeout=15) as conn:
        with conn.cursor() as cur:
            for tbl in (
                "staging.stg_orders",
                "staging.stg_customers",
                "staging.stg_order_events",
            ):
                cur.execute(f"SELECT count(*) FROM {tbl}")
                n = cur.fetchone()[0]
                assert n >= min_n, f"{tbl} count {n} < {min_n}"


@pytest.mark.etl_marts
@pytest.mark.skipif(not _olap_dsn(), reason="ETL_OLAP_DSN not set")
def test_marts_core_tables_exist() -> None:
    import psycopg

    dsn = _olap_dsn()
    assert dsn
    names = (
        "fct_orders",
        "fct_payments",
        "dim_customers",
        "dim_products",
    )
    with psycopg.connect(dsn, connect_timeout=15) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'dwh_marts' AND table_name = ANY(%s)
                """,
                (list(names),),
            )
            found = {r[0] for r in cur.fetchall()}
    missing = set(names) - found
    assert not missing, f"missing dwh_marts tables: {missing}"
