from __future__ import annotations

from app.core.errors import DbtWebError


def validate_manifest(manifest: dict) -> None:
    required = ("metadata", "nodes", "sources")
    missing = [k for k in required if k not in manifest]
    if missing:
        raise DbtWebError("MANIFEST_SCHEMA_ERROR", "manifest missing required keys", details={"missing": missing})
