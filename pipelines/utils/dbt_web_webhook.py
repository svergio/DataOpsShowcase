from __future__ import annotations

import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import requests

from services.common.logging_utils import get_logger

logger = get_logger(__name__)

EVENT_INGESTION_COMPLETED = "ingestion_completed"
EVENT_DATAVAULT_COMPLETED = "datavault_completed"
EVENT_MARTS_COMPLETED = "marts_completed"


def _base_url() -> str:
    return os.environ.get("DBT_WEB_BASE_URL", "http://dbt-web-backend:8000").rstrip("/")


def _headers() -> dict[str, str]:
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    token = os.environ.get("DBT_WEB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _build_event_id(dag_id: str, run_id: str | None, event: str) -> str:
    seed = f"{dag_id}|{run_id or '-'}|{event}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, seed))


def notify_dbt_web(
    *,
    event: str,
    dag_id: str,
    run_id: str | None = None,
    target_layer: str | None = None,
    upstream_run_ref: str | None = None,
    timeout: float = 5.0,
    max_attempts: int = 3,
    backoff_seconds: float = 2.0,
) -> dict[str, Any]:
    """Fire-and-forget HTTP POST to dbt-web events endpoint.

    Idempotency: deterministic event_id derived from (dag_id, run_id, event).
    Retries: bounded with linear backoff. Failures are logged but never raised
    to avoid breaking parent DAG execution.
    """
    base = _base_url()
    if not base:
        logger.warning("dbt-web base URL not configured; skipping webhook")
        return {"status": "skipped", "reason": "no_base_url"}

    url = f"{base}/api/v1/events/{event}"
    payload = {
        "event_id": _build_event_id(dag_id, run_id, event),
        "dag_id": dag_id,
        "run_id": run_id,
        "event_ts": datetime.now(tz=timezone.utc).isoformat(),
        "target_layer": target_layer,
        "upstream_run_ref": upstream_run_ref,
    }
    last_err: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.post(url, json=payload, headers=_headers(), timeout=timeout)
            if 200 <= response.status_code < 300:
                logger.info(
                    "dbt-web webhook delivered",
                    extra={"extra_payload": {"event": event, "attempt": attempt, "url": url}},
                )
                return {"status": "ok", "attempt": attempt, "event_id": payload["event_id"]}
            logger.warning(
                "dbt-web webhook non-2xx",
                extra={
                    "extra_payload": {
                        "event": event,
                        "attempt": attempt,
                        "status_code": response.status_code,
                    }
                },
            )
        except requests.RequestException as exc:
            last_err = exc
            logger.warning(
                "dbt-web webhook attempt failed",
                extra={"extra_payload": {"event": event, "attempt": attempt, "error": str(exc)}},
            )
        time.sleep(backoff_seconds * attempt)
    logger.error(
        "dbt-web webhook gave up",
        extra={"extra_payload": {"event": event, "attempts": max_attempts, "error": str(last_err)}},
    )
    return {"status": "failed", "attempts": max_attempts, "event_id": payload["event_id"]}
