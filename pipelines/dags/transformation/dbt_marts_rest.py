from __future__ import annotations

from datetime import datetime, timezone

from airflow.decorators import dag, task

from pipelines.dags.transformation._dbt_common import run_dbt_layer
from pipelines.utils.dag_factory import default_args
from pipelines.utils.datasets import DS_DBT_MARTS_DONE, DS_DBT_VAULT_DONE
from pipelines.utils.dbt_web_webhook import EVENT_MARTS_COMPLETED, notify_dbt_web

DAG_ID = "dag_dbt_marts_rest"


@dag(
    dag_id=DAG_ID,
    description="Trigger dbt marts models via REST API + docs generate",
    schedule=[DS_DBT_VAULT_DONE],
    start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    default_args=default_args({"retries": 5}),
    tags=["dbt", "marts", "rest", "docs"],
)
def dbt_marts_rest() -> None:
    @task(retries=2)
    def run() -> dict:
        return run_dbt_layer(dag_id=DAG_ID, layer="marts")

    @task(retries=1)
    def docs(_payload: dict) -> dict:
        return run_dbt_layer(dag_id=DAG_ID, layer="docs")

    @task(outlets=[DS_DBT_MARTS_DONE])
    def publish(payload: dict, docs_payload: dict) -> dict:
        notify_dbt_web(
            event=EVENT_MARTS_COMPLETED,
            dag_id=DAG_ID,
            run_id=str(payload.get("run_id") or ""),
            target_layer="marts",
            upstream_run_ref=str(docs_payload.get("run_id") or ""),
        )
        return {
            "dag": DAG_ID,
            "status": "published",
            "marts_run_id": payload.get("run_id"),
            "docs_run_id": docs_payload.get("run_id"),
            **payload,
        }

    marts_payload = run()
    docs_payload = docs(marts_payload)
    publish(marts_payload, docs_payload)


dag = dbt_marts_rest()
