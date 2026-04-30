"""Manual smoke DAG scaffolding for Atlas / Debezium Reachability (adjust URLs for your network)."""

from __future__ import annotations

from datetime import datetime

from airflow.decorators import dag
from airflow.operators.python import PythonOperator


def _atlas_probe() -> None:
    import os
    import urllib.error
    import urllib.request

    url = os.environ.get("ATLAS_REST_URL", "http://atlas_server:21000/")
    try:
        urllib.request.urlopen(url, timeout=5).read(64)
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Atlas unreachable at {url}") from exc


def _kafka_connect_probe() -> None:
    import os
    import urllib.error
    import urllib.request

    url = os.environ.get("DEBEZIUM_CONNECT_HEALTH_URL", "http://debezium_connect:8083/")
    try:
        urllib.request.urlopen(url, timeout=5).read(64)
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Kafka Connect unreachable at {url}") from exc


@dag(
    dag_id="atlas_cdc_integration_touchpoint",
    schedule=None,
    start_date=datetime(2025, 1, 1),
    tags=["integration", "metadata", "cdc"],
    catchup=False,
)
def atlas_cdc_touchpoint():
    t_atlas = PythonOperator(task_id="probe_atlas", python_callable=_atlas_probe)
    t_kafka = PythonOperator(task_id="probe_kafka_connect", python_callable=_kafka_connect_probe)
    t_atlas >> t_kafka


dag = atlas_cdc_touchpoint()
