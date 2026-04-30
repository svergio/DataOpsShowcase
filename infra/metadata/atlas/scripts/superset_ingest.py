#!/usr/bin/env python3
"""REST reachability check for Superset plus optional Atlas entity_publish for superset_lineage.yml."""

from __future__ import annotations

import argparse
import pathlib
import sys
import urllib.request

_ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT))

from entity_publish import load_entities_from_yaml, post_entity


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--superset-base-url", default="http://localhost:8088/")
    p.add_argument("--atlas-base-url", default="")
    p.add_argument("--yaml", type=pathlib.Path, default=None)
    p.add_argument("--user", default="admin")
    p.add_argument("--password", default="admin")
    args = p.parse_args()

    urllib.request.urlopen(args.superset_base_url, timeout=5)
    print("superset: OK", args.superset_base_url)

    if args.yaml and args.atlas_base_url:
        for ent in load_entities_from_yaml(args.yaml):
            body = {"typeName": ent["typeName"], "attributes": ent.get("attributes") or {}}
            code, text = post_entity(args.atlas_base_url, args.user, args.password, body)
            print(f"{code}: {text[:400]}")


if __name__ == "__main__":
    main()
