from __future__ import annotations

from datetime import datetime, timezone

from airflow.decorators import dag, task

from pipelines.utils.dag_factory import default_args
from pipelines.utils.datasets import DS_DQ_PASSED, DS_SERVING_OPTIMIZED

DAG_ID = "dag_serving_optimizations"


@dag(
    dag_id=DAG_ID,
    description="Marts post-load optimizations: indexes, VACUUM ANALYZE, REINDEX",
    schedule=[DS_DQ_PASSED],
    start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    default_args=default_args(),
    tags=["serving", "marts", "optimization"],
)
def serving_optimizations() -> None:
    @task(retries=2)
    def ensure_marts_indexes() -> dict:
        from services.common.config_loader import load_yaml
        from services.common.run_metadata import finish_run, start_run
        from services.serving.optimizer import ensure_indexes

        cfg = load_yaml("serving")
        run_meta = start_run(dag_id=DAG_ID, task_id="ensure_marts_indexes", source="serving", layer="serving")
        try:
            count = ensure_indexes(cfg.get("conn_id", "postgres_dwh"), cfg.get("indexes", []))
            finish_run(run_meta, status="success", payload={"indexes": count})
            return {"indexes_ensured": count}
        except Exception as exc:
            finish_run(run_meta, status="failed", error_message=str(exc))
            raise

    @task(retries=2)
    def vacuum_analyze_marts() -> dict:
        from services.common.config_loader import load_yaml
        from services.common.run_metadata import finish_run, start_run
        from services.serving.optimizer import vacuum_analyze

        cfg = load_yaml("serving")
        run_meta = start_run(dag_id=DAG_ID, task_id="vacuum_analyze_marts", source="serving", layer="serving")
        try:
            vacuum_analyze(cfg.get("conn_id", "postgres_dwh"), cfg.get("vacuum_analyze", []))
            finish_run(run_meta, status="success", payload={"tables": cfg.get("vacuum_analyze", [])})
            return {"tables": cfg.get("vacuum_analyze", [])}
        except Exception as exc:
            finish_run(run_meta, status="failed", error_message=str(exc))
            raise

    @task(retries=1)
    def reindex_marts() -> dict:
        from services.common.config_loader import load_yaml
        from services.common.run_metadata import finish_run, start_run
        from services.serving.optimizer import reindex

        cfg = load_yaml("serving")
        run_meta = start_run(dag_id=DAG_ID, task_id="reindex_marts", source="serving", layer="serving")
        try:
            reindex(cfg.get("conn_id", "postgres_dwh"), cfg.get("reindex", []))
            finish_run(run_meta, status="success", payload={"tables": cfg.get("reindex", [])})
            return {"tables": cfg.get("reindex", [])}
        except Exception as exc:
            finish_run(run_meta, status="failed", error_message=str(exc))
            raise

    @task(outlets=[DS_SERVING_OPTIMIZED])
    def publish(payloads: list[dict]) -> dict:
        return {"dag": DAG_ID, "status": "published", "payloads": payloads}

    indexes = ensure_marts_indexes()
    vacuum = vacuum_analyze_marts()
    reindex_task = reindex_marts()
    indexes >> vacuum >> reindex_task >> publish([indexes, vacuum, reindex_task])


dag = serving_optimizations()
