#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:
    raise SystemExit("pip install PyYAML") from exc


_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_JSON = _REPO_ROOT / "configs" / "generators" / "company.generator.json"


def _topic_entities(
    *,
    cluster: str,
    network_tag: str,
    bootstrap_uri: str,
    topic_key: str,
    topic_val: str,
) -> tuple[dict[str, Any], ...]:
    qn = f"kafka://{cluster}@{network_tag}/{topic_val}"
    return (
        {
            "typeName": "kafka_topic",
            "attributes": {
                "name": f"gen.{topic_key}",
                "topic": topic_val,
                "qualifiedName": qn,
                "uri": f"{bootstrap_uri.rstrip('/')}/{topic_val}",
            },
        },
    )


def _load_topics(cfg: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    prefix = "kafka_topic_"
    for k, v in cfg.items():
        if isinstance(k, str) and k.startswith(prefix) and isinstance(v, str) and v.strip():
            env_override = os.environ.get(k.upper())
            if isinstance(env_override, str) and env_override.strip():
                out[k] = env_override.strip()
            elif isinstance(v, str) and v.strip():
                out[k] = v.strip()
    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Emit kafka_topic YAML for Atlas from generator JSON + env overrides (KAFKA_TOPIC_*)."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=_DEFAULT_JSON,
        help="Path to company.generator.json",
    )
    parser.add_argument(
        "--cluster",
        default=os.environ.get("ATLAS_KAFKA_CLUSTER_ID", "dataops"),
        help="Cluster id encoded in kafka_topic qualifiedName",
    )
    parser.add_argument(
        "--network",
        default=os.environ.get("ATLAS_KAFKA_NETWORK_TAG", "dataops_net"),
        help="Network tag in kafka_topic qualifiedName",
    )
    parser.add_argument(
        "--bootstrap-uri",
        default=os.environ.get("ATLAS_KAFKA_URI_PREFIX", "kafka://kafka:9092"),
        help="Prefix for kafka_topic.uri broker path fragment",
    )
    parser.add_argument("--output", type=argparse.FileType("w"), default="-")
    args = parser.parse_args()
    cfg = json.loads(Path(args.config).read_text())
    topics = _load_topics(cfg)
    ents: list[dict[str, Any]] = []
    for key in sorted(topics.keys()):
        ents.extend(
            _topic_entities(
                cluster=args.cluster,
                network_tag=args.network,
                bootstrap_uri=args.bootstrap_uri,
                topic_key=key,
                topic_val=topics[key],
            )
        )

    ents.append(
        {
            "typeName": "Process",
            "attributes": {
                "name": "generators_streaming_inventory",
                "qualifiedName": (
                    "process://dataops@generators/"
                    + re.sub(r"[^a-zA-Z0-9._@-]+", "_", str(args.config))
                    + "@stack"
                ),
                "description": (
                    "Synthetic load generator emitting to Kafka topics enumerated in configs/generators; "
                    "related kafka_topic entities are generated alongside."
                ),
            },
        },
    )

    yaml.safe_dump(
        {"entities": ents, "source_config": str(args.config.resolve())},
        args.output,
        sort_keys=False,
        allow_unicode=True,
    )


if __name__ == "__main__":
    main()
