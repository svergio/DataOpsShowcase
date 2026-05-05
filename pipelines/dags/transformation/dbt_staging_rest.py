from __future__ import annotations

from datetime import datetime, timezone

from airflow.decorators import dag, task

from pipelines.dags.transformation._dbt_common import run_dbt_layer
from pipelines.utils.dag_factory import default_args
from pipelines.utils.datasets import DS_DBT_STAGING_DONE, DS_VAULT_SCD2_DONE

DAG_ID = "dag_dbt_staging_rest"


@dag(
    dag_id=DAG_ID,
    description="Trigger dbt staging models via REST API with polling, retries and log capture",
    schedule=[DS_VAULT_SCD2_DONE],
    start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    default_args=default_args({"retries": 5}),
    tags=["dbt", "staging", "rest"],
)
def dbt_staging_rest() -> None:
    @task(retries=1)
    def freshness() -> dict:
        return run_dbt_layer(dag_id=DAG_ID, layer="freshness")

    @task(retries=2)
    def run(_freshness_payload: dict) -> dict:
        return run_dbt_layer(dag_id=DAG_ID, layer="staging")

    @task(outlets=[DS_DBT_STAGING_DONE])
    def publish(payload: dict) -> dict:
        return {"dag": DAG_ID, "status": "published", **payload}

    publish(run(freshness()))


dag = dbt_staging_rest()
