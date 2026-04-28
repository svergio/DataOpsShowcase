from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict

log = logging.getLogger("infrastructure.settings.company_profile")


def _normalize_settings_payload(raw: Any) -> Dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            log.warning("Could not parse JSON settings string: %s", exc)
            return {}
        if isinstance(parsed, dict):
            return parsed
        log.warning(
            "JSON settings decoded to unsupported type=%s expected dict",
            type(parsed).__name__,
        )
        return {}
    log.warning(
        "settings payload has unsupported type=%s expected dict",
        type(raw).__name__,
    )
    return {}


def _bool_env(name: str) -> bool:
    val = os.getenv(name)
    if val is None:
        return False
    return val.strip().lower() in {"1", "true", "yes", "y", "on"}


def _load_json_file(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
            return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("Could not load generator JSON profile %s: %s", path, exc)
        return {}


def _load_env_json_overlay() -> Dict[str, Any]:
    raw = os.getenv("GENERATOR_SETTINGS_JSON")
    if raw is None or str(raw).strip() == "":
        return {}
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            log.info(
                "Loaded generator overlay from GENERATOR_SETTINGS_JSON (%s keys)",
                len(data),
            )
            return data
        log.warning(
            "GENERATOR_SETTINGS_JSON must be a JSON object, got=%s",
            type(data).__name__,
        )
    except json.JSONDecodeError as exc:
        log.warning("Could not parse GENERATOR_SETTINGS_JSON: %s", exc)
    return {}


def load_json_profile() -> Dict[str, Any]:
    explicit = os.getenv("GENERATOR_SETTINGS_FILE")
    cfg_dir = os.getenv("GENERATOR_CONFIG_DIR", "/app/configs/generators")
    ordered: list[Path] = []
    if explicit:
        ordered.append(Path(explicit))
    ordered.append(Path(cfg_dir) / "company.generator.json")
    merged_files: Dict[str, Any] = {}
    for p in ordered:
        d = _load_json_file(p)
        if d:
            merged_files = dict(d)
            log.info("Loaded generator profile JSON from %s", p)
            break

    overlay = _load_env_json_overlay()
    if overlay:
        out = dict(merged_files)
        out.update(overlay)
        return out
    return merged_files


def _load_meta_overrides() -> Dict[str, Any]:
    if not _bool_env("GENERATOR_USE_META_STORE"):
        return {}
    dsn = os.getenv("GENERATOR_META_DSN")
    if not dsn:
        log.warning("GENERATOR_USE_META_STORE set but GENERATOR_META_DSN is empty")
        return {}
    profile = os.getenv("GENERATOR_PROFILE", "default")
    try:
        import psycopg
    except ImportError:
        log.warning("psycopg not available for meta store")
        return {}
    try:
        with psycopg.connect(dsn, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT settings FROM generator.config_overrides WHERE profile = %s",
                    (profile,),
                )
                row = cur.fetchone()
                if not row or row[0] is None:
                    return {}
                return _normalize_settings_payload(row[0])
    except Exception as exc:
        log.warning("Meta store override load failed: %s", exc)
        return {}


def load_merged_profile(baseline: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(baseline)
    merged.update(load_json_profile())
    merged.update(_load_meta_overrides())
    return merged
