import os
from dataclasses import dataclass


def _bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "y", "on"}


def _int(name: str, default: int) -> int:
    val = os.getenv(name)
    if val is None or val == "":
        return default
    try:
        return int(val)
    except ValueError:
        return default


@dataclass(frozen=True)
class Config:
    mode: str
    tick_seconds: int
    seed: int
    seed_users: int
    seed_sellers: int
    seed_products: int
    orders_min: int
    orders_max: int
    clicks_min: int
    clicks_max: int
    minio_batch_ticks: int

    enable_oltp: bool
    enable_kafka: bool
    enable_redis: bool
    enable_minio: bool

    oltp_dsn: str

    kafka_bootstrap: str
    kafka_topic_clickstream: str
    kafka_topic_orders: str
    kafka_topic_payments: str
    kafka_topic_shipments: str

    redis_url: str
    redis_channel_orders: str
    redis_channel_payments: str
    redis_channel_clickstream: str
    redis_stream_orders: str

    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket_raw: str
    minio_prefix_payments: str
    minio_prefix_returns: str
    minio_prefix_catalog: str


def load_config() -> Config:
    return Config(
        mode=os.getenv("GENERATOR_MODE", "streaming"),
        tick_seconds=_int("GENERATOR_TICK_SECONDS", 2),
        seed=_int("GENERATOR_SEED", 42),
        seed_users=_int("GENERATOR_SEED_USERS", 200),
        seed_sellers=_int("GENERATOR_SEED_SELLERS", 25),
        seed_products=_int("GENERATOR_SEED_PRODUCTS", 300),
        orders_min=_int("GENERATOR_ORDERS_PER_TICK_MIN", 2),
        orders_max=_int("GENERATOR_ORDERS_PER_TICK_MAX", 8),
        clicks_min=_int("GENERATOR_CLICKS_PER_TICK_MIN", 20),
        clicks_max=_int("GENERATOR_CLICKS_PER_TICK_MAX", 120),
        minio_batch_ticks=_int("GENERATOR_MINIO_BATCH_TICKS", 15),
        enable_oltp=_bool("GENERATOR_ENABLE_OLTP", True),
        enable_kafka=_bool("GENERATOR_ENABLE_KAFKA", True),
        enable_redis=_bool("GENERATOR_ENABLE_REDIS", True),
        enable_minio=_bool("GENERATOR_ENABLE_MINIO", True),
        oltp_dsn=os.getenv(
            "OLTP_DSN",
            "postgresql://oltp_user:oltp_pass@postgres_oltp:5432/techmart_oltp",
        ),
        kafka_bootstrap=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"),
        kafka_topic_clickstream=os.getenv(
            "KAFKA_TOPIC_CLICKSTREAM", "techmart.events.clickstream"
        ),
        kafka_topic_orders=os.getenv("KAFKA_TOPIC_ORDERS", "techmart.events.orders"),
        kafka_topic_payments=os.getenv(
            "KAFKA_TOPIC_PAYMENTS", "techmart.payments.transactions"
        ),
        kafka_topic_shipments=os.getenv(
            "KAFKA_TOPIC_SHIPMENTS", "techmart.shipments.tracking"
        ),
        redis_url=os.getenv("REDIS_URL", "redis://redis:6379/0"),
        redis_channel_orders=os.getenv("REDIS_CHANNEL_ORDERS", "techmart:orders"),
        redis_channel_payments=os.getenv(
            "REDIS_CHANNEL_PAYMENTS", "techmart:payments"
        ),
        redis_channel_clickstream=os.getenv(
            "REDIS_CHANNEL_CLICKSTREAM", "techmart:clickstream"
        ),
        redis_stream_orders=os.getenv(
            "REDIS_STREAM_ORDERS", "techmart:stream:orders"
        ),
        minio_endpoint=os.getenv("MINIO_ENDPOINT", "minio:9000"),
        minio_access_key=os.getenv("MINIO_ACCESS_KEY", "minio"),
        minio_secret_key=os.getenv("MINIO_SECRET_KEY", "minio123"),
        minio_bucket_raw=os.getenv("MINIO_BUCKET_RAW", "techmart-data"),
        minio_prefix_payments=os.getenv("MINIO_PREFIX_PAYMENTS", "raw/payments"),
        minio_prefix_returns=os.getenv("MINIO_PREFIX_RETURNS", "raw/returns"),
        minio_prefix_catalog=os.getenv("MINIO_PREFIX_CATALOG", "raw/product_catalog"),
    )
