from __future__ import annotations

from datetime import datetime, timezone

from airflow.decorators import dag, task

from pipelines.utils.dag_factory import default_args
from pipelines.utils.datasets import DS_DBT_MARTS_DONE, DS_DQ_PASSED

DAG_ID = "dag_data_quality_checks"


@dag(
    dag_id=DAG_ID,
    description="Run uniqueness/null/range/referential/SCD2 invariants and fail on critical issues",
    schedule=[DS_DBT_MARTS_DONE],
    start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    default_args=default_args(),
    tags=["quality", "dq"],
)
def data_quality_checks() -> None:
    @task(retries=2)
    def execute_checks() -> dict:
        from services.common.config_loader import load_yaml
        from services.common.run_metadata import finish_run, start_run
        from services.quality.checks import execute_checks as run_checks

        cfg = load_yaml("dq_checks")
        run_meta = start_run(dag_id=DAG_ID, task_id="execute_checks", source="dq", layer="quality")
        try:
            results, failures = run_checks(
                dag_id=DAG_ID,
                checks=cfg["checks"],
                fail_on=cfg.get("fail_on", ["critical"]),
            )
            payload = {
                "checks_total": len(results),
                "checks_passed": sum(1 for r in results if r.passed),
                "checks_failed": sum(1 for r in results if not r.passed),
                "blocking_failures": [r.name for r in failures],
            }
            if failures:
                finish_run(
                    run_meta,
                    status="failed",
                    error_message=f"DQ blocking failures: {[r.name for r in failures]}",
                    payload=payload,
                )
                raise ValueError(f"DQ blocking failures: {[r.name for r in failures]}")
            finish_run(run_meta, status="success", payload=payload)
            return payload
        except Exception as exc:
            finish_run(run_meta, status="failed", error_message=str(exc))
            raise

    @task(outlets=[DS_DQ_PASSED])
    def publish(payload: dict) -> dict:
        return {"dag": DAG_ID, "status": "published", **payload}

    publish(execute_checks())


dag = data_quality_checks()
