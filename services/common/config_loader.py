from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

CONFIG_DIR_ENV = "DATAOPS_CONFIG_DIR"
DEFAULT_CONFIG_DIR = Path("/opt/airflow/configs/pipeline")


def get_config_dir() -> Path:
    raw = os.environ.get(CONFIG_DIR_ENV)
    if raw:
        return Path(raw)
    return DEFAULT_CONFIG_DIR


@lru_cache(maxsize=64)
def load_yaml(name: str) -> dict[str, Any]:
    path = get_config_dir() / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"pipeline config not found: {path}")
    with path.open("r", encoding="utf-8") as fp:
        return yaml.safe_load(fp) or {}


def env(name: str, default: str | None = None, *, required: bool = False) -> str | None:
    value = os.environ.get(name, default)
    if required and not value:
        raise RuntimeError(f"required env var {name} is missing")
    return value


def resolve_env_value(spec: dict[str, Any], env_key: str = "env", default_key: str = "default") -> str:
    env_name = spec.get(env_key)
    if env_name:
        value = os.environ.get(env_name)
        if value:
            return value
    fallback = spec.get(default_key)
    if fallback is None:
        raise RuntimeError(
            f"unable to resolve env-backed config: env={env_name} default missing"
        )
    return str(fallback)


def reset_cache() -> None:
    load_yaml.cache_clear()
