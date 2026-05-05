#!/usr/bin/env python3
"""
Cross-check portal services/portal_web/data/catalog.json container names against
docker-compose.yml container_name fields.

Optional-only services: containers tied to graph nodes with `"optional": true`
are excluded from the strict check when absent from compose (e.g. profile-only `data_generator`).

Usage (from repo root):
  python scripts/portal_catalog_lint.py
  python scripts/portal_catalog_lint.py path/to/docker-compose.yml path/to/catalog.json

Requires: PyYAML (pip install pyyaml), or use same venv as Airflow local tools.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def _compose_container_names(compose_path: Path) -> set[str]:
    try:
        import yaml
    except ImportError as exc:
        raise SystemExit(
            "PyYAML is required: pip install pyyaml"
        ) from exc
    data = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    services = data.get("services") or {}
    names: set[str] = set()
    for _svc, cfg in services.items():
        if not isinstance(cfg, dict):
            continue
        cn = cfg.get("container_name")
        if cn:
            names.add(str(cn))
    return names


def _catalog_containers_and_allow_missing(catalog_path: Path) -> tuple[set[str], set[str]]:
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    out: set[str] = set()
    allow: set[str] = set()
    for block in ("web_ui_services", "api_and_tools"):
        for row in data.get(block) or []:
            c = row.get("container")
            if c:
                out.add(str(c))
    for n in data.get("graph_nodes") or []:
        c = n.get("container")
        if c:
            out.add(str(c))
        if n.get("optional") and c:
            allow.add(str(c))
    return out, allow


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    compose = Path(sys.argv[1]) if len(sys.argv) > 1 else root / "docker-compose.yml"
    catalog = Path(sys.argv[2]) if len(sys.argv) > 2 else root / "services" / "portal_web" / "data" / "catalog.json"
    if not compose.is_file():
        print(f"missing compose: {compose}", file=sys.stderr)
        return 2
    if not catalog.is_file():
        print(f"missing catalog: {catalog}", file=sys.stderr)
        return 2

    compose_names = _compose_container_names(compose)
    cat_names, allow_missing = _catalog_containers_and_allow_missing(catalog)
    missing = sorted(cat_names - compose_names - allow_missing)
    if missing:
        print("Catalog references container_name not found in docker-compose.yml:", file=sys.stderr)
        for m in missing:
            print(f"  - {m}", file=sys.stderr)
        print(
            "\n(Containers marked optional on graph nodes in catalog are skipped when not in compose.)",
            file=sys.stderr,
        )
        return 1
    print("OK: all catalog container names exist in docker-compose container_name entries.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
