#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:
    raise SystemExit("pip install PyYAML") from exc


DEFAULT_MANIFEST_PATH = Path(__file__).resolve().parents[4] / "dbt" / "target" / "manifest.json"


def _model_nodes(payload: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in payload.get("nodes", {}).items() if v.get("resource_type") == "model"}


def main() -> None:
    p = argparse.ArgumentParser(description="Atlas hive_db/hive_table YAML derived from dbt manifest.json.")
    p.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST_PATH,
        help="Path to manifest.json produced by dbt docs generate/run.",
    )
    p.add_argument(
        "--cluster",
        default="dataops",
        help="@{cluster} suffix for hive_* qualifiedNames.",
    )
    p.add_argument("--output", type=argparse.FileType("w"), default="-")
    args = p.parse_args()
    if not args.manifest.is_file():
        raise SystemExit(f"manifest missing: {args.manifest}")

    raw = json.loads(args.manifest.read_text())
    nodes = _model_nodes(raw)
    databases = sorted(
        {(n.get("database") or "").strip() for n in nodes.values()}
        .difference({""}),
    )

    entities: list[dict[str, Any]] = []

    cluster = args.cluster

    def qn(db: str) -> str:
        return f"{db}@{cluster}"

    for db in databases:
        entities.append(
            {
                "typeName": "hive_db",
                "attributes": {
                    "name": db,
                    "qualifiedName": qn(db),
                    "clusterName": cluster,
                    "description": "dbt-managed models materialized against this analytical database.",
                },
            },
        )

    for node_id, node in sorted(nodes.items(), key=lambda kv: kv[0]):
        db = (node.get("database") or "").strip()
        sch = (node.get("schema") or "").strip()
        name = (node.get("name") or "").strip()
        deps = sorted(node.get("depends_on", {}).get("nodes") or [])
        if not db or not sch or not name:
            continue
        qtbl = f"{db}.{sch}.{name}"
        dep_note = "; ".join(deps[:10]) + ("..." if len(deps) > 10 else "") if deps else "none"
        entities.append(
            {
                "typeName": "hive_table",
                "relationshipAttributes": {
                    "db": {
                        "typeName": "hive_db",
                        "uniqueAttributes": {"qualifiedName": qn(db)},
                    },
                },
                "attributes": {
                    "name": name,
                    "qualifiedName": f"{qtbl}@{cluster}",
                    "description": f"dbt model {node_id}; depends_on_nodes {dep_note}",
                },
            },
        )

    report = {"entities": entities, "source": str(args.manifest), "cluster": cluster, "models": len(nodes)}
    yaml.safe_dump(report, args.output, sort_keys=False, allow_unicode=True)


if __name__ == "__main__":
    main()
