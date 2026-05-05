from __future__ import annotations

from typing import Any

from airflow.utils.context import Context


def _base_payload(context: Context) -> dict[str, Any]:
    dag = context.get("dag")
    ti = context.get("ti")
    dr = context.get("dag_run")
    logical = context.get("logical_date") or context.get("data_interval_end")
    return {
        "dag_id": dag.dag_id if dag else None,
        "task_id": context.get("task").task_id if context.get("task") else None,
        "run_id": dr.run_id if dr else None,
        "map_index": ti.map_index if ti and ti.map_index is not None else None,
        "execution_date": str(logical) if logical is not None else None,
        "try_number": ti.try_number if ti else None,
    }


def task_failure_callback(context: Context) -> None:
    from services.common.logging_utils import get_logger
    from services.common.metrics import record_airflow_task_outcome

    payload = _base_payload(context)
    exc = context.get("exception")
    payload["event"] = "task_failure"
    payload["error"] = str(exc) if exc else None

    get_logger("airflow.callback").error(
        "airflow_task_failure",
        extra={"extra_payload": payload},
    )
    if payload.get("dag_id") and payload.get("task_id"):
        try:
            record_airflow_task_outcome(
                dag_id=str(payload["dag_id"]),
                task_id=str(payload["task_id"]),
                success=False,
            )
        except Exception:
            pass


def task_success_callback(context: Context) -> None:
    from services.common.logging_utils import get_logger
    from services.common.metrics import record_airflow_task_outcome

    payload = _base_payload(context)
    payload["event"] = "task_success"
    get_logger("airflow.callback").info(
        "airflow_task_success",
        extra={"extra_payload": payload},
    )
    if payload.get("dag_id") and payload.get("task_id"):
        try:
            record_airflow_task_outcome(
                dag_id=str(payload["dag_id"]),
                task_id=str(payload["task_id"]),
                success=True,
            )
        except Exception:
            pass
