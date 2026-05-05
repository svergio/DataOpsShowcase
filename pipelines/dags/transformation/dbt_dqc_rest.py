from __future__ import annotations

from datetime import datetime, timezone

from airflow.decorators import dag, task

from pipelines.dags.transformation._dbt_common import run_dbt_layer
from pipelines.utils.dag_factory import default_args
from pipelines.utils.datasets import DS_DBT_DQC_DONE, DS_DBT_MARTS_DONE

DAG_ID = "dag_dbt_dqc_rest"


@dag(
    dag_id=DAG_ID,
    description="Run all dbt data tests (selector dqc_all_tests) via dbt-rest after marts build",
    schedule=[DS_DBT_MARTS_DONE],
    start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    default_args=default_args({"retries": 3}),
    tags=["dbt", "dqc", "rest"],
)
def dbt_dqc_rest() -> None:
    @task(retries=2, outlets=[DS_DBT_DQC_DONE])
    def run_dqc() -> dict:
        return run_dbt_layer(dag_id=DAG_ID, layer="dqc")

    run_dqc()


dag = dbt_dqc_rest()
