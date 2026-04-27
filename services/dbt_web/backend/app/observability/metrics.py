from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

MODELS_TOTAL = Gauge("dbt_web_models_total", "Total dbt resources in cache index")
BROKEN_TESTS_TOTAL = Gauge("dbt_web_tests_broken_total", "Number of failed tests from latest run")
FRESHNESS_LAG_SECONDS = Gauge(
    "dbt_web_freshness_lag_seconds",
    "Freshness lag in seconds",
    ["source", "table"],
)
RUN_DURATION_SECONDS = Histogram(
    "dbt_web_run_duration_seconds",
    "dbt run duration in seconds",
    ["target"],
    buckets=(5, 15, 30, 60, 120, 300, 600, 1200, 1800, 3600),
)
RUN_OUTCOME_TOTAL = Counter(
    "dbt_web_run_outcome_total",
    "dbt run outcomes by status",
    ["target", "status"],
)
TEST_FAILURE_RATE = Gauge(
    "dbt_web_test_failure_rate",
    "Failed tests / total tests for last run (per target)",
    ["target"],
)
INGESTION_LAG_SECONDS = Gauge(
    "dbt_web_ingestion_lag_seconds",
    "Lag between source updated_at and ingestion completion",
    ["pipeline"],
)
KAFKA_OFFSET_LAG = Gauge(
    "dbt_web_kafka_offset_lag",
    "Difference between latest Kafka offset and last consumed",
    ["topic", "partition"],
)
CACHE_HITS_TOTAL = Counter("dbt_web_artifact_cache_hits_total", "Artifact cache hits", ["target"])
CACHE_MISS_TOTAL = Counter("dbt_web_artifact_cache_miss_total", "Artifact cache misses", ["target"])
UPSTREAM_ERRORS_TOTAL = Counter(
    "dbt_web_upstream_errors_total",
    "Upstream DBT REST errors",
    ["operation"],
)
WEBHOOK_EVENTS_TOTAL = Counter(
    "dbt_web_webhook_events_total",
    "Webhook events received from Airflow",
    ["event", "status"],
)
