from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.integration

pytest.importorskip("psycopg")
pytest.importorskip("redis")
pytest.importorskip("confluent_kafka")
pytest.importorskip("minio")


def _dsn_pg() -> str | None:
    return os.getenv("GENERATOR_IT_OLTP_DSN")


def _redis_url() -> str | None:
    return os.getenv("GENERATOR_IT_REDIS_URL")


def _kafka_bootstrap() -> str | None:
    return os.getenv("GENERATOR_IT_KAFKA_BOOTSTRAP")


def _minio_params() -> tuple[str, str, str] | None:
    ep = os.getenv("GENERATOR_IT_MINIO_ENDPOINT")
    ak = os.getenv("GENERATOR_IT_MINIO_ACCESS_KEY")
    sk = os.getenv("GENERATOR_IT_MINIO_SECRET_KEY")
    if not ep or ak is None or sk is None:
        return None
    return ep, ak, sk


@pytest.mark.skipif(not _dsn_pg(), reason="GENERATOR_IT_OLTP_DSN not set")
def test_postgres_connect_select_one() -> None:
    import psycopg

    dsn = _dsn_pg()
    assert dsn
    with psycopg.connect(dsn, connect_timeout=10) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            assert cur.fetchone() == (1,)


@pytest.mark.skipif(not _redis_url(), reason="GENERATOR_IT_REDIS_URL not set")
def test_redis_ping() -> None:
    import redis

    r = redis.Redis.from_url(_redis_url(), socket_connect_timeout=10)
    assert r.ping() is True


@pytest.mark.skipif(not _kafka_bootstrap(), reason="GENERATOR_IT_KAFKA_BOOTSTRAP not set")
def test_kafka_cluster_reachable() -> None:
    from confluent_kafka import KafkaException
    from confluent_kafka.admin import AdminClient

    bootstrap = _kafka_bootstrap()
    admin = AdminClient(
        {"bootstrap.servers": bootstrap, "socket.timeout.ms": 10000},
    )
    try:
        md = admin.list_topics(timeout=15)
    except KafkaException as exc:
        pytest.fail(f"Kafka admin could not reach cluster at {bootstrap}: {exc}")
    assert len(md.brokers) > 0, (
        "cluster metadata returned no brokers; bootstrap URL may be wrong or unreachable"
    )


@pytest.mark.skipif(not _minio_params(), reason="GENERATOR_IT_MINIO_* not set")
def test_minio_list_buckets() -> None:
    from minio import Minio

    endpoint, ak, sk = _minio_params()  # type: ignore[misc]
    use_tls = os.getenv("GENERATOR_IT_MINIO_SECURE", "").lower() in {"1", "true", "yes"}
    client = Minio(endpoint, access_key=ak, secret_key=sk, secure=use_tls)
    client.list_buckets()
