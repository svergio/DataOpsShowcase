from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any, Iterator

from airflow.providers.postgres.hooks.postgres import PostgresHook

from services.common.logging_utils import get_logger

logger = get_logger(__name__)

CONN_ID = "postgres_dwh"
TABLE = "meta.pipeline_runs"


@contextmanager
def _cursor() -> Iterator[Any]:
    hook = PostgresHook(postgres_conn_id=CONN_ID)
    conn = hook.get_conn()
    try:
        with conn.cursor() as cursor:
            yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def start_run(
    *,
    dag_id: str,
    task_id: str,
    source: str | None = None,
    layer: str | None = None,
    payload: dict[str, Any] | None = None,
) -> int:
    sql = f"""
        INSERT INTO {TABLE} (dag_id, task_id, source, layer, status, payload)
        VALUES (%s, %s, %s, %s, 'running', %s)
        RETURNING run_id
    """
    with _cursor() as cur:
        cur.execute(sql, (dag_id, task_id, source, layer, json.dumps(payload or {})))
        run_id = cur.fetchone()[0]
    logger.info(
        "pipeline run started",
        extra={"extra_payload": {"run_id": run_id, "dag_id": dag_id, "task_id": task_id}},
    )
    return int(run_id)


def finish_run(
    run_id: int,
    *,
    status: str = "success",
    rows_in: int | None = None,
    rows_out: int | None = None,
    rows_quarantined: int | None = None,
    error_message: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    sql = f"""
        UPDATE {TABLE}
        SET finished_at = NOW(),
            status = %s,
            rows_in = %s,
            rows_out = %s,
            rows_quarantined = %s,
            error_message = %s,
            payload = COALESCE(payload, '{{}}'::jsonb) || %s::jsonb
        WHERE run_id = %s
    """
    with _cursor() as cur:
        cur.execute(
            sql,
            (
                status,
                rows_in,
                rows_out,
                rows_quarantined,
                error_message,
                json.dumps(payload or {}),
                run_id,
            ),
        )
    logger.info(
        "pipeline run finished",
        extra={
            "extra_payload": {
                "run_id": run_id,
                "status": status,
                "rows_in": rows_in,
                "rows_out": rows_out,
                "rows_quarantined": rows_quarantined,
            }
        },
    )
