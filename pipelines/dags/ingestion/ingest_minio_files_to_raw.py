from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from airflow.decorators import dag, task, task_group

from pipelines.utils.dag_factory import default_args
from pipelines.utils.datasets import DS_RAW_MINIO_FILES

DAG_ID = "dag_ingest_minio_files_to_raw"
SCHEDULE = "*/15 * * * *"
MAX_FILES_DEFAULT = 200


@dag(
    dag_id=DAG_ID,
    description="MinIO file landing zone -> raw with manifest tracking and quarantine",
    schedule=SCHEDULE,
    start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    default_args=default_args(),
    tags=["ingestion", "minio", "files"],
)
def ingest_minio_files_to_raw() -> None:
    @task
    def discover_new_files() -> list[dict[str, Any]]:
        from services.common.config_loader import load_yaml
        from services.common.logging_utils import get_logger
        from services.storage.minio_io import (
            get_client,
            list_objects,
        )
        from services.storage.postgres_io import bulk_insert, fetch_all

        logger = get_logger(DAG_ID)
        cfg = load_yaml("ingestion")["minio"]
        bucket = os.environ.get(cfg["bucket_env"])
        if not bucket:
            raise RuntimeError(f"env {cfg['bucket_env']} is not configured")
        client = get_client(
            endpoint=os.environ.get(cfg["endpoint_env"]),
            access_key=os.environ.get(cfg["access_key_env"]),
            secret_key=os.environ.get(cfg["secret_key_env"]),
        )
        known = {
            row[0]
            for row in fetch_all(
                "postgres_dwh", f"SELECT file_path FROM {cfg['state_table']}"
            )
        }
        discovered: list[dict[str, Any]] = []
        for prefix_cfg in cfg["prefixes"]:
            prefix = os.environ.get(prefix_cfg["prefix_env"])
            if not prefix:
                continue
            for obj in list_objects(client, bucket, prefix):
                if obj.key in known:
                    continue
                discovered.append(
                    {
                        "file_path": obj.key,
                        "prefix": prefix,
                        "bucket": bucket,
                        "size_bytes": obj.size,
                        "etag": obj.etag,
                        "file_format": prefix_cfg["file_format"],
                    }
                )
        if discovered:
            bulk_insert(
                "postgres_dwh",
                cfg["state_table"],
                ["file_path", "prefix", "bucket", "size_bytes", "etag", "status", "payload"],
                [
                    (
                        d["file_path"],
                        d["prefix"],
                        d["bucket"],
                        d["size_bytes"],
                        d["etag"],
                        "discovered",
                        json.dumps({"file_format": d["file_format"]}),
                    )
                    for d in discovered
                ],
                on_conflict="ON CONFLICT (file_path) DO NOTHING",
            )
        max_files = int(cfg.get("max_files_per_run", MAX_FILES_DEFAULT))
        sliced = discovered[:max_files]
        logger.info(
            "minio discovered files",
            extra={
                "extra_payload": {
                    "discovered": len(discovered),
                    "scheduled": len(sliced),
                }
            },
        )
        return sliced

    @task_group(group_id="ingest_files")
    def ingest_group(files: list[dict[str, Any]]) -> None:
        @task(retries=3)
        def ingest_file(meta: dict[str, Any]) -> dict[str, Any]:
            from services.common.config_loader import load_yaml
            from services.common.logging_utils import get_logger
            from services.common.run_metadata import finish_run, start_run
            from services.storage.minio_io import (
                get_client,
                read_csv,
                read_jsonl,
            )
            from services.storage.postgres_io import bulk_insert, execute

            logger = get_logger(DAG_ID)
            cfg = load_yaml("ingestion")["minio"]
            run_meta = start_run(
                dag_id=DAG_ID,
                task_id="ingest_file",
                source="minio.files",
                layer="ingestion",
                payload={"file": meta["file_path"], "prefix": meta["prefix"]},
            )
            try:
                client = get_client(
                    endpoint=os.environ.get(cfg["endpoint_env"]),
                    access_key=os.environ.get(cfg["access_key_env"]),
                    secret_key=os.environ.get(cfg["secret_key_env"]),
                )
                if meta["file_format"] == "jsonl":
                    rows = read_jsonl(client, meta["bucket"], meta["file_path"])
                elif meta["file_format"] == "csv":
                    rows = read_csv(client, meta["bucket"], meta["file_path"])
                else:
                    raise ValueError(f"unsupported file_format: {meta['file_format']}")
                inserted_payments = 0
                if "payments" in meta["prefix"] and rows:
                    payment_rows = []
                    for row in rows:
                        event_uuid = (
                            f"{meta['file_path']}::{row.get('payment_id') or row.get('event_id') or len(payment_rows)}"
                        )
                        payment_rows.append(
                            (
                                event_uuid,
                                meta["file_path"],
                                row.get("payment_id"),
                                row.get("order_id"),
                                row.get("amount"),
                                (row.get("currency") or "")[:3] or None,
                                row.get("status"),
                                row.get("event_ts") or row.get("ts"),
                            )
                        )
                    inserted_payments = bulk_insert(
                        "postgres_dwh",
                        "staging.stg_minio_payments",
                        [
                            "event_uuid",
                            "source_file",
                            "payment_id",
                            "order_id",
                            "amount",
                            "currency",
                            "status",
                            "event_ts",
                        ],
                        payment_rows,
                        on_conflict="ON CONFLICT (event_uuid) DO NOTHING",
                    )
                rows_loaded = inserted_payments or len(rows)
                update_sql = (
                    f"UPDATE {cfg['state_table']} "
                    "SET status = %s, rows_loaded = %s, loaded_at = NOW() "
                    "WHERE file_path = %s"
                )
                execute("postgres_dwh", update_sql, ("loaded", rows_loaded, meta["file_path"]))
                finish_run(
                    run_meta,
                    status="success",
                    rows_in=len(rows),
                    rows_out=rows_loaded,
                    payload={"file_format": meta["file_format"]},
                )
                logger.info(
                    "minio file ingested",
                    extra={
                        "extra_payload": {
                            "file": meta["file_path"],
                            "rows": rows_loaded,
                        }
                    },
                )
                return {"file": meta["file_path"], "rows": rows_loaded}
            except Exception as exc:
                logger.exception(
                    "minio file ingestion failed",
                    extra={"extra_payload": {"file": meta["file_path"], "error": str(exc)}},
                )
                quarantine_sql = (
                    f"UPDATE {cfg['state_table']} "
                    "SET status = %s, payload = COALESCE(payload, '{}'::jsonb) || %s::jsonb "
                    "WHERE file_path = %s"
                )
                from services.storage.postgres_io import execute as pg_exec

                pg_exec(
                    "postgres_dwh",
                    quarantine_sql,
                    ("quarantined", json.dumps({"error": str(exc)}), meta["file_path"]),
                )
                finish_run(run_meta, status="failed", error_message=str(exc))
                raise

        ingest_file.expand(meta=files)

    @task(outlets=[DS_RAW_MINIO_FILES])
    def publish(_: Any = None, airflow_run_ref: str = "{{ run_id }}") -> dict:
        from services.common.logging_utils import get_logger

        get_logger(DAG_ID).info(
            "minio raw signal",
            extra={"extra_payload": {"dag": DAG_ID}},
        )
        return {"dag": DAG_ID, "status": "published"}

    files = discover_new_files()
    ingest_group(files) >> publish()


dag = ingest_minio_files_to_raw()
