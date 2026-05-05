from __future__ import annotations

import logging
import time

import mlflow
from mlflow.tracking import MlflowClient

logger = logging.getLogger(__name__)

_CACHE_TTL_SEC = 60.0
_cache: dict[str, tuple[bool, float]] = {}


def _cache_key(tracking_uri: str, model_uri: str, model_name: str) -> str:
    return f"{tracking_uri}|{model_uri}|{model_name}"


def resolve_registry_model_name(model_uri: str, fallback_name: str) -> str:
    if model_uri.startswith("models:/"):
        rest = model_uri[len("models:/") :].strip("/")
        if rest:
            name = rest.split("/")[0].strip()
            if name:
                return name
    return fallback_name


def is_model_registered(
    *,
    tracking_uri: str,
    model_uri: str,
    model_name: str,
    use_cache: bool = True,
) -> bool:
    key = _cache_key(tracking_uri, model_uri, model_name)
    now = time.monotonic()
    if use_cache and key in _cache:
        ok, ts = _cache[key]
        if now - ts < _CACHE_TTL_SEC:
            return ok

    name = resolve_registry_model_name(model_uri, model_name)
    mlflow.set_tracking_uri(tracking_uri)
    client = MlflowClient(tracking_uri)
    ok = False
    try:
        versions = client.search_model_versions(
            filter_string=f"name='{name}'",
            max_results=1,
        )
        ok = len(versions) > 0
    except Exception as exc:  # noqa: BLE001
        logger.warning("mlflow_registry_check_failed name=%s error=%s", name, exc)
        ok = False

    _cache[key] = (ok, now)
    return ok
