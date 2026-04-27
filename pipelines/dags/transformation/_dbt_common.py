from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from services.common.config_loader import load_yaml
from services.common.logging_utils import get_logger
from services.common.metrics import record_dbt_run_duration
from services.common.run_metadata import finish_run, start_run
from services.dbt_client.rest_client import DbtRunFailed, DbtRunRequest, build_client_from_config

logger = get_logger(__name__)


def _parse_iso(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        return None


def run_dbt_layer(*, dag_id: str, layer: str) -> dict[str, Any]:
    cfg = load_yaml("dbt_rest")
    layer_cfg = cfg["runs"].get(layer)
    if not layer_cfg:
        raise ValueError(f"dbt layer not configured: {layer}")
    client = build_client_from_config(cfg.get("connection", {}), cfg.get("retry", {}))
    request = DbtRunRequest(
        job_name=layer_cfg["job_name"],
        selectors=list(layer_cfg.get("selectors", [])),
        target=layer_cfg.get("target", "dwh"),
        fail_on_test_failure=bool(layer_cfg.get("fail_on_test_failure", True)),
        command=layer_cfg.get("command"),
    )
    run_meta = start_run(
        dag_id=dag_id,
        task_id=f"dbt.{layer}",
        source=f"dbt.{layer}",
        layer="dbt",
        payload={"job": request.job_name, "selectors": request.selectors},
    )
    started_monotonic = time.monotonic()
    try:
        result = client.run_and_wait(request)
        started_at_dt = _parse_iso(result.started_at)
        finished_at_dt = _parse_iso(result.finished_at)
        if started_at_dt and finished_at_dt:
            duration_seconds = max(0.0, (finished_at_dt - started_at_dt).total_seconds())
        else:
            duration_seconds = max(0.0, time.monotonic() - started_monotonic)
        record_dbt_run_duration(target=layer, duration_seconds=duration_seconds, status="success")
        payload = {
            "run_id": result.run_id,
            "status": result.status,
            "started_at": result.started_at,
            "finished_at": result.finished_at,
            "artifacts_url": result.artifacts_url,
            "duration_seconds": duration_seconds,
        }
        finish_run(run_meta, status="success", payload=payload)
        logger.info("dbt layer succeeded", extra={"extra_payload": payload})
        return payload
    except DbtRunFailed as exc:
        record_dbt_run_duration(
            target=layer,
            duration_seconds=max(0.0, time.monotonic() - started_monotonic),
            status="failed",
        )
        finish_run(
            run_meta,
            status="failed",
            error_message=f"dbt run {exc.run_id} status={exc.status}",
            payload={"run_id": exc.run_id, "status": exc.status},
        )
        raise
    except Exception as exc:
        record_dbt_run_duration(
            target=layer,
            duration_seconds=max(0.0, time.monotonic() - started_monotonic),
            status="error",
        )
        finish_run(run_meta, status="failed", error_message=str(exc))
        raise
