from __future__ import annotations

from datetime import datetime, timezone

from airflow.decorators import dag, task, task_group

from pipelines.utils.dag_factory import default_args
from pipelines.utils.datasets import DS_STG_CLEAN, DS_VAULT_LOADED

DAG_ID = "dag_load_datavault"
SOURCE = "vault.load"


@dag(
    dag_id=DAG_ID,
    description="Load Hubs and Links into Data Vault from staging (idempotent, hash-keyed)",
    schedule=[DS_STG_CLEAN],
    start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    default_args=default_args(),
    tags=["vault", "transformation"],
)
def load_datavault() -> None:
    @task_group(group_id="hubs")
    def hubs_group() -> None:
        @task(retries=3)
        def load_hub_customers() -> dict:
            from services.common.run_metadata import finish_run, start_run
            from services.vault.loaders import load_hub

            run_meta = start_run(dag_id=DAG_ID, task_id="hubs.hub_customers", source=SOURCE, layer="vault")
            try:
                stats = load_hub("hub_customers")
                finish_run(run_meta, status="success", rows_out=stats.inserted)
                return {"hub": stats.name, "inserted": stats.inserted}
            except Exception as exc:
                finish_run(run_meta, status="failed", error_message=str(exc))
                raise

        @task(retries=3)
        def load_hub_orders() -> dict:
            from services.common.run_metadata import finish_run, start_run
            from services.vault.loaders import load_hub

            run_meta = start_run(dag_id=DAG_ID, task_id="hubs.hub_orders", source=SOURCE, layer="vault")
            try:
                stats = load_hub("hub_orders")
                finish_run(run_meta, status="success", rows_out=stats.inserted)
                return {"hub": stats.name, "inserted": stats.inserted}
            except Exception as exc:
                finish_run(run_meta, status="failed", error_message=str(exc))
                raise

        load_hub_customers()
        load_hub_orders()

    @task_group(group_id="links")
    def links_group() -> None:
        @task(retries=3)
        def load_link_customer_orders() -> dict:
            from services.common.run_metadata import finish_run, start_run
            from services.vault.loaders import load_link

            run_meta = start_run(
                dag_id=DAG_ID, task_id="links.link_customer_orders", source=SOURCE, layer="vault"
            )
            try:
                stats = load_link("link_customer_orders")
                finish_run(run_meta, status="success", rows_out=stats.inserted)
                return {"link": stats.name, "inserted": stats.inserted}
            except Exception as exc:
                finish_run(run_meta, status="failed", error_message=str(exc))
                raise

        load_link_customer_orders()

    @task
    def vault_summary_metrics() -> dict[str, int]:
        from services.common.logging_utils import get_logger
        from services.vault.loaders import vault_summary

        summary = vault_summary()
        get_logger(DAG_ID).info("vault summary", extra={"extra_payload": summary})
        return summary

    @task(outlets=[DS_VAULT_LOADED])
    def publish_signal(_summary: dict) -> dict:
        return {"dag": DAG_ID, "status": "published"}

    hubs = hubs_group()
    links = links_group()
    summary = vault_summary_metrics()
    hubs >> links >> summary >> publish_signal(summary)


dag = load_datavault()
