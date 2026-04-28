import os
from dataclasses import dataclass
from typing import Any, Dict

from infrastructure.settings.company_profile import load_merged_profile


def _bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "y", "on"}


def _int_env(name: str, default: int) -> int:
    val = os.getenv(name)
    if val is None or val == "":
        return default
    try:
        return int(val)
    except ValueError:
        return default


def _pick_str(env_name: str, merged: Dict[str, Any], key: str, fallback: str) -> str:
    ev = os.getenv(env_name)
    if ev is not None and str(ev).strip() != "":
        return str(ev).strip()
    mv = merged.get(key)
    if mv is not None and str(mv).strip() != "":
        return str(mv).strip()
    return fallback


def _pick_int(env_name: str, merged: Dict[str, Any], key: str, fallback: int) -> int:
    ev = os.getenv(env_name)
    if ev is not None and str(ev).strip() != "":
        try:
            return int(ev.strip())
        except ValueError:
            pass
    mv = merged.get(key)
    if mv is not None:
        try:
            return int(mv)
        except (TypeError, ValueError):
            pass
    return fallback


def _pick_bool(env_name: str, merged: Dict[str, Any], key: str, fallback: bool) -> bool:
    ev = os.getenv(env_name)
    if ev is not None and str(ev).strip() != "":
        return ev.strip().lower() in {"1", "true", "yes", "y", "on"}
    if key in merged and merged[key] is not None:
        v = merged[key]
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return bool(v)
        if isinstance(v, str):
            return v.strip().lower() in {"1", "true", "yes", "y", "on"}
    return fallback


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

    enable_extensions: bool
    generator_config_dir: str
    kafka_topic_marketing_email: str
    kafka_topic_seo_organic: str
    kafka_topic_hr_time_tracking: str
    kafka_topic_feature_flag_eval: str
    minio_prefix_marketing_perf: str
    minio_prefix_seo_rankings: str
    minio_prefix_telemetry_perf: str
    minio_prefix_telemetry_errors: str
    minio_prefix_hr_perf: str
    redis_key_web_vitals_prefix: str


def _baseline() -> Dict[str, Any]:
    return {
        "mode": "streaming",
        "tick_seconds": 2,
        "seed": 42,
        "seed_users": 200,
        "seed_sellers": 25,
        "seed_products": 300,
        "orders_per_tick_min": 2,
        "orders_per_tick_max": 8,
        "clicks_per_tick_min": 20,
        "clicks_per_tick_max": 120,
        "minio_batch_ticks": 15,
        "enable_oltp": True,
        "enable_kafka": True,
        "enable_redis": True,
        "enable_minio": True,
        "enable_extensions": True,
        "generator_config_dir": "/app/configs/generators",
        "kafka_topic_clickstream": "techmart.events.clickstream",
        "kafka_topic_orders": "techmart.events.orders",
        "kafka_topic_payments": "techmart.payments.transactions",
        "kafka_topic_shipments": "techmart.shipments.tracking",
        "redis_channel_orders": "techmart:orders",
        "redis_channel_payments": "techmart:payments",
        "redis_channel_clickstream": "techmart:clickstream",
        "redis_stream_orders": "techmart:stream:orders",
        "minio_bucket_raw": "techmart-data",
        "minio_prefix_payments": "raw/payments",
        "minio_prefix_returns": "raw/returns",
        "minio_prefix_catalog": "raw/product_catalog",
        "kafka_topic_marketing_email": "techmart.marketing.email_events",
        "kafka_topic_seo_organic": "techmart.seo.organic_sessions",
        "kafka_topic_hr_time_tracking": "techmart.hr.time_tracking",
        "kafka_topic_feature_flag_eval": "techmart.features.evaluated",
        "minio_prefix_marketing_perf": "raw/marketing/campaign_performance",
        "minio_prefix_seo_rankings": "raw/seo/rankings",
        "minio_prefix_telemetry_perf": "raw/telemetry/performance",
        "minio_prefix_telemetry_errors": "raw/telemetry/errors",
        "minio_prefix_hr_perf": "raw/hr/performance",
        "redis_key_web_vitals_prefix": "web_vitals:p95",
    }


def load_config() -> Config:
    merged = load_merged_profile(_baseline())
    return Config(
        mode=_pick_str("GENERATOR_MODE", merged, "mode", "streaming"),
        tick_seconds=_pick_int("GENERATOR_TICK_SECONDS", merged, "tick_seconds", 2),
        seed=_pick_int("GENERATOR_SEED", merged, "seed", 42),
        seed_users=_pick_int("GENERATOR_SEED_USERS", merged, "seed_users", 200),
        seed_sellers=_pick_int("GENERATOR_SEED_SELLERS", merged, "seed_sellers", 25),
        seed_products=_pick_int("GENERATOR_SEED_PRODUCTS", merged, "seed_products", 300),
        orders_min=_pick_int("GENERATOR_ORDERS_PER_TICK_MIN", merged, "orders_per_tick_min", 2),
        orders_max=_pick_int("GENERATOR_ORDERS_PER_TICK_MAX", merged, "orders_per_tick_max", 8),
        clicks_min=_pick_int("GENERATOR_CLICKS_PER_TICK_MIN", merged, "clicks_per_tick_min", 20),
        clicks_max=_pick_int("GENERATOR_CLICKS_PER_TICK_MAX", merged, "clicks_per_tick_max", 120),
        minio_batch_ticks=_pick_int("GENERATOR_MINIO_BATCH_TICKS", merged, "minio_batch_ticks", 15),
        enable_oltp=_pick_bool("GENERATOR_ENABLE_OLTP", merged, "enable_oltp", True),
        enable_kafka=_pick_bool("GENERATOR_ENABLE_KAFKA", merged, "enable_kafka", True),
        enable_redis=_pick_bool("GENERATOR_ENABLE_REDIS", merged, "enable_redis", True),
        enable_minio=_pick_bool("GENERATOR_ENABLE_MINIO", merged, "enable_minio", True),
        oltp_dsn=_pick_str(
            "OLTP_DSN",
            merged,
            "oltp_dsn",
            "postgresql://oltp_user:oltp_pass@postgres_oltp:5432/techmart_oltp",
        ),
        kafka_bootstrap=_pick_str(
            "KAFKA_BOOTSTRAP_SERVERS",
            merged,
            "kafka_bootstrap",
            "kafka:9092",
        ),
        kafka_topic_clickstream=_pick_str(
            "KAFKA_TOPIC_CLICKSTREAM",
            merged,
            "kafka_topic_clickstream",
            "techmart.events.clickstream",
        ),
        kafka_topic_orders=_pick_str(
            "KAFKA_TOPIC_ORDERS",
            merged,
            "kafka_topic_orders",
            "techmart.events.orders",
        ),
        kafka_topic_payments=_pick_str(
            "KAFKA_TOPIC_PAYMENTS",
            merged,
            "kafka_topic_payments",
            "techmart.payments.transactions",
        ),
        kafka_topic_shipments=_pick_str(
            "KAFKA_TOPIC_SHIPMENTS",
            merged,
            "kafka_topic_shipments",
            "techmart.shipments.tracking",
        ),
        redis_url=_pick_str(
            "REDIS_URL",
            merged,
            "redis_url",
            "redis://redis:6379/0",
        ),
        redis_channel_orders=_pick_str(
            "REDIS_CHANNEL_ORDERS",
            merged,
            "redis_channel_orders",
            "techmart:orders",
        ),
        redis_channel_payments=_pick_str(
            "REDIS_CHANNEL_PAYMENTS",
            merged,
            "redis_channel_payments",
            "techmart:payments",
        ),
        redis_channel_clickstream=_pick_str(
            "REDIS_CHANNEL_CLICKSTREAM",
            merged,
            "redis_channel_clickstream",
            "techmart:clickstream",
        ),
        redis_stream_orders=_pick_str(
            "REDIS_STREAM_ORDERS",
            merged,
            "redis_stream_orders",
            "techmart:stream:orders",
        ),
        minio_endpoint=_pick_str(
            "MINIO_ENDPOINT",
            merged,
            "minio_endpoint",
            "minio:9000",
        ),
        minio_access_key=_pick_str(
            "MINIO_ACCESS_KEY",
            merged,
            "minio_access_key",
            "minio",
        ),
        minio_secret_key=_pick_str(
            "MINIO_SECRET_KEY",
            merged,
            "minio_secret_key",
            "minio123",
        ),
        minio_bucket_raw=_pick_str(
            "MINIO_BUCKET_RAW",
            merged,
            "minio_bucket_raw",
            "techmart-data",
        ),
        minio_prefix_payments=_pick_str(
            "MINIO_PREFIX_PAYMENTS",
            merged,
            "minio_prefix_payments",
            "raw/payments",
        ),
        minio_prefix_returns=_pick_str(
            "MINIO_PREFIX_RETURNS",
            merged,
            "minio_prefix_returns",
            "raw/returns",
        ),
        minio_prefix_catalog=_pick_str(
            "MINIO_PREFIX_CATALOG",
            merged,
            "minio_prefix_catalog",
            "raw/product_catalog",
        ),
        enable_extensions=_pick_bool("GENERATOR_ENABLE_EXTENSIONS", merged, "enable_extensions", True),
        generator_config_dir=_pick_str(
            "GENERATOR_CONFIG_DIR",
            merged,
            "generator_config_dir",
            "/app/configs/generators",
        ),
        kafka_topic_marketing_email=_pick_str(
            "KAFKA_TOPIC_MARKETING_EMAIL",
            merged,
            "kafka_topic_marketing_email",
            "techmart.marketing.email_events",
        ),
        kafka_topic_seo_organic=_pick_str(
            "KAFKA_TOPIC_SEO_ORGANIC",
            merged,
            "kafka_topic_seo_organic",
            "techmart.seo.organic_sessions",
        ),
        kafka_topic_hr_time_tracking=_pick_str(
            "KAFKA_TOPIC_HR_TIME_TRACKING",
            merged,
            "kafka_topic_hr_time_tracking",
            "techmart.hr.time_tracking",
        ),
        kafka_topic_feature_flag_eval=_pick_str(
            "KAFKA_TOPIC_FEATURE_FLAG_EVAL",
            merged,
            "kafka_topic_feature_flag_eval",
            "techmart.features.evaluated",
        ),
        minio_prefix_marketing_perf=_pick_str(
            "MINIO_PREFIX_MARKETING_PERF",
            merged,
            "minio_prefix_marketing_perf",
            "raw/marketing/campaign_performance",
        ),
        minio_prefix_seo_rankings=_pick_str(
            "MINIO_PREFIX_SEO_RANKINGS",
            merged,
            "minio_prefix_seo_rankings",
            "raw/seo/rankings",
        ),
        minio_prefix_telemetry_perf=_pick_str(
            "MINIO_PREFIX_TELEMETRY_PERF",
            merged,
            "minio_prefix_telemetry_perf",
            "raw/telemetry/performance",
        ),
        minio_prefix_telemetry_errors=_pick_str(
            "MINIO_PREFIX_TELEMETRY_ERRORS",
            merged,
            "minio_prefix_telemetry_errors",
            "raw/telemetry/errors",
        ),
        minio_prefix_hr_perf=_pick_str(
            "MINIO_PREFIX_HR_PERF",
            merged,
            "minio_prefix_hr_perf",
            "raw/hr/performance",
        ),
        redis_key_web_vitals_prefix=_pick_str(
            "REDIS_KEY_WEB_VITALS_PREFIX",
            merged,
            "redis_key_web_vitals_prefix",
            "web_vitals:p95",
        ),
    )
