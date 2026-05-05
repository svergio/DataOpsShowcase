from __future__ import annotations

from prometheus_client import Counter, Histogram

_LABELS = ("status", "stage")

REQUEST_COUNT = Counter(
    "nl2sql_request_count",
    "Total NL2SQL HTTP /query requests completed",
    labelnames=_LABELS,
)

REQUEST_LATENCY_SECONDS = Histogram(
    "nl2sql_request_latency_seconds",
    "End-to-end /query latency in seconds (same as total_latency; kept for compatibility)",
    labelnames=_LABELS,
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0),
)

TOTAL_LATENCY_SECONDS = Histogram(
    "nl2sql_total_latency_seconds",
    "Wall-clock latency of the NL2SQL pipeline in seconds",
    labelnames=_LABELS,
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0),
)

SQL_EXECUTION_LATENCY_SECONDS = Histogram(
    "nl2sql_sql_execution_latency_seconds",
    "Latency of successful SELECT execution in seconds",
    labelnames=_LABELS,
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

SQL_GENERATION_ERRORS = Counter(
    "nl2sql_sql_generation_errors",
    "Failures after exhausting SQL generation retries",
    labelnames=_LABELS,
)

SQL_VALIDATION_ERRORS = Counter(
    "nl2sql_sql_validation_errors",
    "SQL validation failures (per failed attempt)",
    labelnames=_LABELS,
)

SQL_EXECUTION_ERRORS = Counter(
    "nl2sql_sql_execution_errors",
    "Database execution failures for generated SQL",
    labelnames=_LABELS,
)

ROWS_RETURNED = Histogram(
    "nl2sql_rows_returned",
    "Number of rows returned by executed SQL",
    labelnames=_LABELS,
    buckets=(0, 1, 5, 10, 25, 50, 75, 100, 150, 200),
)

RAG_RETRIEVED_TABLES_COUNT = Histogram(
    "nl2sql_rag_retrieved_tables_count",
    "Number of distinct tables retrieved by RAG for a request",
    labelnames=_LABELS,
    buckets=(0, 1, 2, 3, 4, 5, 6),
)

RETRY_TOTAL = Counter(
    "nl2sql_retry_total",
    "Retries after validation or execution failure",
    labelnames=("stage",),
)

CACHE_HIT_TOTAL = Counter(
    "nl2sql_cache_hit_total",
    "Cache hits (reserved; increments when response caching is enabled)",
    labelnames=_LABELS,
)
