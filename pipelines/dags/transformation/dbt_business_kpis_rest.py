from __future__ import annotations

from datetime import datetime, timezone

from airflow.decorators import dag, task

from pipelines.dags.transformation._dbt_common import run_dbt_layer
from pipelines.utils.dag_factory import default_args
from pipelines.utils.datasets import DS_DBT_BUSINESS_KPIS_DONE, DS_DBT_VAULT_DONE

DAG_ID = "dag_dbt_business_kpis_rest"


@dag(
    dag_id=DAG_ID,
    description="Run dbt business KPI marts via REST API",
    schedule=[DS_DBT_VAULT_DONE],
    start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    default_args=default_args({"retries": 4}),
    tags=["dbt", "marts", "business_kpis", "rest"],
)
def dbt_business_kpis_rest() -> None:
    @task(retries=2)
    def run() -> dict:
        return run_dbt_layer(dag_id=DAG_ID, layer="business_kpis")

    @task(outlets=[DS_DBT_BUSINESS_KPIS_DONE])
    def publish(payload: dict) -> dict:
        return {
            "dag": DAG_ID,
            "status": "published",
            "business_kpis_run_id": payload.get("run_id"),
            **payload,
        }

    publish(run())


dag = dbt_business_kpis_rest()
