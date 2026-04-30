from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from airflow.decorators import dag, task, task_group
from airflow.utils.trigger_rule import TriggerRule

from pipelines.utils.dag_factory import default_args, sla_minutes
from pipelines.utils.datasets import DS_RAW_OLTP
from pipelines.utils.dbt_web_webhook import EVENT_INGESTION_COMPLETED, notify_dbt_web


DAG_ID = "dag_ingest_oltp_to_stg"
LAYER = "ingestion"
SOURCE = "oltp"
SCHEDULE = "*/15 * * * *"
DEFAULT_AIRFLOW_RUN_REF = "{{ run_id }}"


def _parse_cursor(raw: str | None, fallback_ts: str) -> tuple[str, Any]:
    """Decode composite watermark stored as JSON {"ts": "...", "pk": <value>}.

    Backward compatible with legacy plain-timestamp watermarks.
    """
    if not raw:
        return fallback_ts, None
    text = raw.strip()
    if text.startswith("{"):
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return text, None
        if isinstance(data, dict) and "ts" in data:
            return str(data["ts"]), data.get("pk")
    return text, None


def _serialize_cursor(ts: str, pk: Any) -> str:
    return json.dumps({"ts": ts, "pk": pk}, default=str, ensure_ascii=False)


@dag(
    dag_id=DAG_ID,
    description="Incremental OLTP -> raw.oltp_* extract with watermarks",
    schedule=SCHEDULE,
    start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    default_args=default_args(),
    tags=["ingestion", "oltp", "source"],
    sla_miss_callback=None,
)
def ingest_oltp_to_stg() -> None:
    @task
    def load_table_specs() -> list[dict[str, Any]]:
        from services.common.config_loader import load_yaml

        cfg = load_yaml("ingestion")["oltp"]
        specs: list[dict[str, Any]] = []
        for table in cfg["tables"]:
            specs.append(
                {
                    "source_table": table["source_table"],
                    "target_table": table["target_table"],
                    "columns": table["columns"],
                    "watermark_column": table.get("watermark_column", cfg.get("watermark_column", "created_at")),
                    "fallback": cfg.get("fallback_watermark", "1970-01-01T00:00:00+00:00"),
                    "batch_size": cfg.get("batch_size", 5000),
                    "pk": table.get("pk"),
                }
            )
        return specs

    @task_group(group_id="extract")
    def extract_group(specs: list[dict[str, Any]]) -> None:
        @task(retries=3)
        def extract_table(spec: dict[str, Any], airflow_run_ref: str = DEFAULT_AIRFLOW_RUN_REF) -> dict[str, Any]:
            from datetime import datetime, timezone

            from services.common.metrics import record_ingestion_lag
            from services.common.run_metadata import finish_run, start_run
            from services.common.watermarks import get_watermark, now_iso, set_watermark
            from services.storage.postgres_io import bulk_insert, fetch_all

            pipeline = f"oltp.{spec['source_table']}"
            run_meta = start_run(
                dag_id=DAG_ID,
                task_id=f"extract.{spec['source_table']}",
                source=SOURCE,
                layer=LAYER,
                payload={"target": spec["target_table"]},
            )
            try:
                watermark_col = spec.get("watermark_column")
                pk_cols: list[str] = list(spec.get("pk") or [])
                pk_col = pk_cols[0] if pk_cols else None
                cols_sql = ", ".join(spec["columns"])
                params: tuple[Any, ...] = ()
                if watermark_col and pk_col and pk_col in spec["columns"]:
                    last_raw = get_watermark(pipeline, fallback=spec["fallback"])
                    last_ts, last_pk = _parse_cursor(last_raw, spec["fallback"])
                    if last_pk is None:
                        where_sql = f"WHERE {watermark_col} > %s"
                        params = (last_ts,)
                    else:
                        where_sql = f"WHERE ({watermark_col}, {pk_col}) > (%s, %s)"
                        params = (last_ts, last_pk)
                    order_sql = f"ORDER BY {watermark_col} ASC, {pk_col} ASC"
                elif watermark_col:
                    last_raw = get_watermark(pipeline, fallback=spec["fallback"])
                    last_ts, _ = _parse_cursor(last_raw, spec["fallback"])
                    where_sql = f"WHERE {watermark_col} > %s"
                    params = (last_ts,)
                    order_sql = f"ORDER BY {watermark_col} ASC"
                else:
                    where_sql = ""
                    order_sql = f"ORDER BY {pk_col or spec['columns'][0]} ASC"
                sql = (
                    f"SELECT {cols_sql} FROM {spec['source_table']} {where_sql} "
                    f"{order_sql} LIMIT {spec['batch_size']}"
                )
                rows = fetch_all("postgres_oltp", sql, params)
                rows_with_meta = [(*row, airflow_run_ref) for row in rows]
                target_columns = list(spec["columns"]) + ["source_run_id"]
                inserted = bulk_insert(
                    "postgres_dwh",
                    spec["target_table"],
                    target_columns,
                    rows_with_meta,
                    page_size=1000,
                )
                new_watermark: str | None = None
                if watermark_col and pk_col and pk_col in spec["columns"] and rows:
                    wm_index = spec["columns"].index(watermark_col)
                    pk_index = spec["columns"].index(pk_col)
                    last_row = rows[-1]
                    new_ts_val = last_row[wm_index]
                    new_ts = (
                        new_ts_val.isoformat() if hasattr(new_ts_val, "isoformat") else str(new_ts_val)
                    )
                    new_pk_val = last_row[pk_index]
                    new_watermark = _serialize_cursor(new_ts, new_pk_val)
                    set_watermark(pipeline, new_watermark, records_processed=inserted)
                elif watermark_col and rows:
                    wm_index = spec["columns"].index(watermark_col)
                    new_value = max(row[wm_index] for row in rows if row[wm_index] is not None)
                    new_watermark = (
                        new_value.isoformat() if hasattr(new_value, "isoformat") else str(new_value)
                    )
                    set_watermark(pipeline, new_watermark, records_processed=inserted)
                finish_run(
                    run_meta,
                    status="success",
                    rows_in=len(rows),
                    rows_out=inserted,
                    payload={"watermark": new_watermark},
                )
                if watermark_col and rows:
                    try:
                        wm_index = spec["columns"].index(watermark_col)
                        last_val = rows[-1][wm_index]
                        last_dt = (
                            last_val
                            if isinstance(last_val, datetime)
                            else datetime.fromisoformat(str(last_val).replace("Z", "+00:00"))
                        )
                        if last_dt.tzinfo is None:
                            last_dt = last_dt.replace(tzinfo=timezone.utc)
                        lag_seconds = (datetime.now(timezone.utc) - last_dt).total_seconds()
                        record_ingestion_lag(pipeline=pipeline, lag_seconds=lag_seconds)
                    except Exception:  # noqa: BLE001
                        pass
                return {
                    "table": spec["source_table"],
                    "rows": inserted,
                    "watermark": new_watermark or now_iso(),
                }
            except Exception as exc:
                finish_run(run_meta, status="failed", error_message=str(exc))
                raise

        extract_table.expand(spec=specs)

    @task(outlets=[DS_RAW_OLTP], trigger_rule=TriggerRule.NONE_FAILED)
    def publish_signal(airflow_run_ref: str = DEFAULT_AIRFLOW_RUN_REF) -> dict[str, Any]:
        from services.common.logging_utils import get_logger

        logger = get_logger(DAG_ID)
        logger.info(
            "raw oltp signal emitted",
            extra={"extra_payload": {"dag": DAG_ID, "dataset": "raw_oltp"}},
        )
        notify_dbt_web(
            event=EVENT_INGESTION_COMPLETED,
            dag_id=DAG_ID,
            run_id=airflow_run_ref,
            target_layer="raw.oltp",
        )
        return {"dag": DAG_ID, "status": "published"}

    specs = load_table_specs()
    extract = extract_group(specs)
    extract >> publish_signal()


dag = ingest_oltp_to_stg()
