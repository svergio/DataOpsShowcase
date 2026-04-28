from __future__ import annotations

import os
from typing import Any

from services.common.logging_utils import get_logger

logger = get_logger(__name__)

_REGISTRY: Any = None
_GAUGES: dict[str, Any] = {}
_COUNTERS: dict[str, Any] = {}
_HISTS: dict[str, Any] = {}


def _enabled() -> bool:
    return bool(os.environ.get("PROMETHEUS_PUSHGATEWAY_URL"))


def _import_prom() -> tuple[Any, Any, Any, Any, Any] | None:
    try:
        from prometheus_client import (
            CollectorRegistry,
            Counter,
            Gauge,
            Histogram,
            push_to_gateway,
        )
    except Exception:  # noqa: BLE001
        return None
    return CollectorRegistry, Counter, Gauge, Histogram, push_to_gateway


def _registry() -> Any:
    global _REGISTRY
    if _REGISTRY is None:
        mods = _import_prom()
        if mods is None:
            return None
        CollectorRegistry, *_ = mods
        _REGISTRY = CollectorRegistry()
    return _REGISTRY


def _gauge(name: str, doc: str, labels: tuple[str, ...]) -> Any:
    if name in _GAUGES:
        return _GAUGES[name]
    mods = _import_prom()
    if mods is None:
        return None
    _, _, Gauge, _, _ = mods
    g = Gauge(name, doc, list(labels), registry=_registry())
    _GAUGES[name] = g
    return g


def _counter(name: str, doc: str, labels: tuple[str, ...]) -> Any:
    if name in _COUNTERS:
        return _COUNTERS[name]
    mods = _import_prom()
    if mods is None:
        return None
    _, Counter, _, _, _ = mods
    c = Counter(name, doc, list(labels), registry=_registry())
    _COUNTERS[name] = c
    return c


def _histogram(name: str, doc: str, labels: tuple[str, ...], buckets: tuple[float, ...]) -> Any:
    if name in _HISTS:
        return _HISTS[name]
    mods = _import_prom()
    if mods is None:
        return None
    _, _, _, Histogram, _ = mods
    h = Histogram(name, doc, list(labels), buckets=list(buckets), registry=_registry())
    _HISTS[name] = h
    return h


def _push(job: str, grouping_key: dict[str, str] | None = None) -> None:
    if not _enabled():
        return
    mods = _import_prom()
    if mods is None:
        return
    _, _, _, _, push_to_gateway = mods
    url = os.environ["PROMETHEUS_PUSHGATEWAY_URL"]
    try:
        push_to_gateway(url, job=job, registry=_registry(), grouping_key=grouping_key or {})
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "pushgateway push failed",
            extra={"extra_payload": {"job": job, "error": str(exc), "url": url}},
        )


def record_ingestion_lag(*, pipeline: str, lag_seconds: float, job: str = "airflow_ingestion") -> None:
    g = _gauge("dataops_ingestion_lag_seconds", "Ingestion lag in seconds", ("pipeline",))
    if g is None:
        return
    g.labels(pipeline=pipeline).set(max(0.0, lag_seconds))
    _push(job=job, grouping_key={"pipeline": pipeline})


def record_kafka_offset_lag(*, topic: str, partition: int, lag: int, job: str = "airflow_kafka") -> None:
    g = _gauge(
        "dataops_kafka_offset_lag",
        "Kafka offset lag (latest - last_consumed)",
        ("topic", "partition"),
    )
    if g is None:
        return
    g.labels(topic=topic, partition=str(partition)).set(max(0, int(lag)))
    _push(job=job, grouping_key={"topic": topic, "partition": str(partition)})


def record_dbt_run_duration(*, target: str, duration_seconds: float, status: str) -> None:
    h = _histogram(
        "dataops_dbt_run_duration_seconds",
        "dbt run duration in seconds",
        ("target", "status"),
        buckets=(5, 15, 30, 60, 120, 300, 600, 1200, 1800, 3600),
    )
    c = _counter(
        "dataops_dbt_run_outcome_total",
        "dbt run outcomes",
        ("target", "status"),
    )
    if h is not None:
        h.labels(target=target, status=status).observe(max(0.0, duration_seconds))
    if c is not None:
        c.labels(target=target, status=status).inc()
    _push(job="airflow_dbt", grouping_key={"target": target})


def record_dbt_test_failures(*, target: str, total: int, failed: int) -> None:
    g = _gauge("dataops_dbt_test_failures_total", "Failed dbt tests in last run", ("target",))
    g_total = _gauge("dataops_dbt_tests_total", "Total dbt tests in last run", ("target",))
    if g is None or g_total is None:
        return
    g.labels(target=target).set(max(0, int(failed)))
    g_total.labels(target=target).set(max(0, int(total)))
    _push(job="airflow_dbt", grouping_key={"target": target})


def record_freshness_lag(*, source: str, table: str, lag_seconds: float) -> None:
    g = _gauge(
        "dataops_freshness_lag_seconds",
        "Source freshness lag in seconds",
        ("source", "table"),
    )
    if g is None:
        return
    g.labels(source=source, table=table).set(max(0.0, lag_seconds))
    _push(job="airflow_freshness", grouping_key={"source": source, "table": table})


def record_airflow_task_outcome(*, dag_id: str, task_id: str, success: bool) -> None:
    name = "dag_success" if success else "dag_failure"
    doc = "Airflow task finished successfully" if success else "Airflow task failed"
    c = _counter(name, doc, ("dag_id", "task_id"))
    if c is None:
        return
    c.labels(dag_id=dag_id, task_id=task_id).inc()
    _push(job="airflow_task_outcomes")


def record_airflow_task_duration(*, dag_id: str, task_id: str, duration_seconds: float) -> None:
    h = _histogram(
        "task_duration_seconds",
        "Airflow task duration in seconds",
        ("dag_id", "task_id"),
        buckets=(0.1, 0.5, 1, 5, 30, 60, 120, 300, 600, 1800),
    )
    if h is None:
        return
    h.labels(dag_id=dag_id, task_id=task_id).observe(max(0.0, float(duration_seconds)))
    _push(job="airflow_task_durations")
