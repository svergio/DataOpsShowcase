from __future__ import annotations

from datetime import datetime, timezone

from airflow.decorators import dag, task

from pipelines.dags.transformation._dbt_common import run_dbt_layer
from pipelines.utils.dag_factory import default_args
from pipelines.utils.datasets import (
    DS_DBT_STAGING_DONE,
    DS_DBT_VAULT_DONE,
    DS_RAW_KAFKA_EXTENSIONS,
)
from pipelines.utils.dbt_web_webhook import EVENT_DATAVAULT_COMPLETED, notify_dbt_web

DAG_ID = "dag_dbt_vault_rest"


@dag(
    dag_id=DAG_ID,
    description="Trigger dbt vault models via REST API",
    schedule=(DS_DBT_STAGING_DONE | DS_RAW_KAFKA_EXTENSIONS),
    start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    default_args=default_args({"retries": 5}),
    tags=["dbt", "vault", "rest"],
)
def dbt_vault_rest() -> None:
    @task(retries=2)
    def run() -> dict:
        return run_dbt_layer(dag_id=DAG_ID, layer="vault")

    @task(outlets=[DS_DBT_VAULT_DONE])
    def publish(payload: dict) -> dict:
        notify_dbt_web(
            event=EVENT_DATAVAULT_COMPLETED,
            dag_id=DAG_ID,
            run_id=str(payload.get("run_id") or ""),
            target_layer="vault",
        )
        return {"dag": DAG_ID, "status": "published", **payload}

    publish(run())


dag = dbt_vault_rest()
