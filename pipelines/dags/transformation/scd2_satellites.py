from __future__ import annotations

from datetime import datetime, timezone

from airflow.decorators import dag, task, task_group

from pipelines.utils.dag_factory import default_args
from pipelines.utils.datasets import DS_VAULT_LOADED, DS_VAULT_SCD2_DONE

DAG_ID = "dag_scd2_satellites"
SOURCE = "vault.scd2"


@dag(
    dag_id=DAG_ID,
    description="SCD2 Satellites historization with late-arriving reconciliation",
    schedule=[DS_VAULT_LOADED],
    start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    default_args=default_args(),
    tags=["vault", "scd2"],
)
def scd2_satellites() -> None:
    @task_group(group_id="satellites")
    def sats_group() -> None:
        @task(retries=3)
        def load_sat_customer_details() -> dict:
            from services.common.run_metadata import finish_run, start_run
            from services.vault.loaders import load_satellite_scd2, reconcile_late_arriving

            run_meta = start_run(
                dag_id=DAG_ID,
                task_id="satellites.sat_customer_details",
                source=SOURCE,
                layer="vault",
            )
            try:
                stats = load_satellite_scd2("sat_customer_details")
                fixed = reconcile_late_arriving("sat_customer_details")
                finish_run(
                    run_meta,
                    status="success",
                    rows_out=stats.inserted,
                    payload={"late_arriving_rows_fixed": fixed},
                )
                return {"sat": stats.name, "inserted": stats.inserted, "reconciled": fixed}
            except Exception as exc:
                finish_run(run_meta, status="failed", error_message=str(exc))
                raise

        @task(retries=3)
        def load_sat_order_status() -> dict:
            from services.common.run_metadata import finish_run, start_run
            from services.vault.loaders import load_satellite_scd2, reconcile_late_arriving

            run_meta = start_run(
                dag_id=DAG_ID,
                task_id="satellites.sat_order_status",
                source=SOURCE,
                layer="vault",
            )
            try:
                stats = load_satellite_scd2("sat_order_status")
                fixed = reconcile_late_arriving("sat_order_status")
                finish_run(
                    run_meta,
                    status="success",
                    rows_out=stats.inserted,
                    payload={"late_arriving_rows_fixed": fixed},
                )
                return {"sat": stats.name, "inserted": stats.inserted, "reconciled": fixed}
            except Exception as exc:
                finish_run(run_meta, status="failed", error_message=str(exc))
                raise

        load_sat_customer_details()
        load_sat_order_status()

    @task
    def validate_scd2() -> dict:
        from services.storage.postgres_io import fetch_one

        violations = {}
        for table, hk in (
            ("vault.sat_customer_details", "customer_hk"),
            ("vault.sat_order_status", "order_hk"),
        ):
            row = fetch_one(
                "postgres_dwh",
                f"""
                    SELECT COUNT(*) FROM (
                        SELECT {hk}, COUNT(*) AS c
                        FROM {table}
                        WHERE is_current = TRUE
                        GROUP BY {hk}
                        HAVING COUNT(*) > 1
                    ) v
                """,
            )
            violations[table] = int(row[0]) if row else 0
        if any(violations.values()):
            raise ValueError(f"SCD2 invariant violation: {violations}")
        return violations

    @task(outlets=[DS_VAULT_SCD2_DONE])
    def publish_signal(_validation: dict) -> dict:
        return {"dag": DAG_ID, "status": "published"}

    sats = sats_group()
    validation = validate_scd2()
    sats >> validation >> publish_signal(validation)


dag = scd2_satellites()
