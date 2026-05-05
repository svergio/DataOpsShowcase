from __future__ import annotations

import os
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any

REPO_ROOT = Path("/opt/airflow")
SERVICES_PATH = REPO_ROOT / "services"
CONFIG_PATH = REPO_ROOT / "configs" / "pipeline"

for path in (str(REPO_ROOT), str(SERVICES_PATH.parent)):
    if path not in sys.path:
        sys.path.insert(0, path)

DEFAULT_ARGS_BASE = {
    "owner": "dataops-platform",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=30),
}


def default_args(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    args = dict(DEFAULT_ARGS_BASE)
    if overrides:
        args.update(overrides)
    return args


def heavy_pipeline_default_args(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    args = default_args(
        {
            "max_active_runs": 1,
            "retries": 3,
        }
    )
    if overrides:
        args.update(overrides)
    return args


def smtp_aware_default_args(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    args = default_args()
    recipient = os.environ.get("AIRFLOW_ALERT_EMAIL") or os.environ.get("AIRFLOW_SMTP_RECIPIENT")
    if recipient and os.environ.get("AIRFLOW_SMTP_ENABLED", "").strip().lower() in ("1", "true", "yes"):
        args = dict(args)
        args["email"] = [recipient]
        args["email_on_failure"] = True
    if overrides:
        args.update(overrides)
    return args


def sla_minutes(value: int) -> timedelta:
    return timedelta(minutes=value)
