from __future__ import annotations

from airflow.listeners import hookimpl

from services.common.metrics import record_airflow_task_duration, record_airflow_task_outcome


def _duration_seconds(task_instance) -> float:
    try:
        d = task_instance.duration
        if d is None:
            return 0.0
        if hasattr(d, "total_seconds"):
            return max(0.0, float(d.total_seconds()))
        return max(0.0, float(d))
    except Exception:  # noqa: BLE001
        return 0.0


@hookimpl
def on_task_instance_success(previous_state, task_instance, session=None):  # noqa: ARG001
    dag_id = task_instance.dag_id
    task_id = task_instance.task_id
    record_airflow_task_outcome(dag_id=dag_id, task_id=task_id, success=True)
    record_airflow_task_duration(dag_id=dag_id, task_id=task_id, duration_seconds=_duration_seconds(task_instance))


@hookimpl
def on_task_instance_failed(previous_state, task_instance, session=None):  # noqa: ARG001
    dag_id = task_instance.dag_id
    task_id = task_instance.task_id
    record_airflow_task_outcome(dag_id=dag_id, task_id=task_id, success=False)
    record_airflow_task_duration(dag_id=dag_id, task_id=task_id, duration_seconds=_duration_seconds(task_instance))
