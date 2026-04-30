#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

import yaml

_REQUIRED_ATTRS: dict[str, tuple[str, ...]] = {
    "Process": ("name", "qualifiedName"),
    "kafka_topic": ("name", "topic", "qualifiedName", "uri"),
    "hive_db": ("name", "qualifiedName", "clusterName"),
    "hive_table": ("name", "qualifiedName"),
}


def auth_header_basic(user: str, password: str) -> str:
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return f"Basic {token}"


def _request_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str],
    data: bytes | None = None,
    timeout_s: float = 30,
) -> tuple[int, dict[str, Any] | None, str]:
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode()
            if not raw.strip():
                return resp.status, None, ""
            return resp.status, json.loads(raw), raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        try:
            return e.code, json.loads(raw) if raw.strip() else None, raw
        except json.JSONDecodeError:
            return e.code, None, raw


def get_entity_guid_by_qualified_name(
    base_url: str, user: str, password: str, type_name: str, qualified_name: str
) -> str | None:
    qs = urlencode({"attr:qualifiedName": qualified_name})
    path = f"/api/atlas/v2/entity/uniqueAttribute/type/{quote(type_name)}"
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}?{qs}"
    headers = {"Authorization": auth_header_basic(user, password)}
    code, data, _ = _request_json("GET", url, headers=headers)
    if code == 404:
        return None
    if code >= 400 or not data:
        return None
    entity = data.get("entity") or {}
    gid = entity.get("guid") or ""
    return gid or None


def post_entity(
    base_url: str, user: str, password: str, body: dict[str, Any], timeout_s: float = 30
) -> tuple[int, str]:
    url = base_url.rstrip("/") + "/api/atlas/v2/entity"
    data = json.dumps({"entity": body}).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": auth_header_basic(user, password),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def load_entities_from_yaml(path: Path) -> list[dict[str, Any]]:
    doc = yaml.safe_load(path.read_text()) or {}
    out = list(doc.get("entities") or [])
    if not out and doc.get("process"):
        p = doc["process"]
        out = [
            {
                "typeName": "Process",
                "attributes": {
                    "name": p.get("name", "process"),
                    "qualifiedName": p["qualifiedName"],
                    "description": p.get("description", ""),
                },
            }
        ]
    return out


def qualified_name_key(ent: dict[str, Any]) -> str | None:
    attrs = ent.get("attributes") or {}
    q = attrs.get("qualifiedName")
    if isinstance(q, str) and q.strip():
        return q.strip()
    return None


def validate_entities(entities: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    seen: set[tuple[str, str]] = set()
    for i, ent in enumerate(entities):
        tn = ent.get("typeName")
        if not tn:
            errors.append(f"entities[{i}]: missing typeName")
            continue
        qn = qualified_name_key(ent)
        if not qn:
            errors.append(f"entities[{i}]: missing attributes.qualifiedName")
        else:
            key = (str(tn), qn)
            if key in seen:
                errors.append(f"duplicate qualifiedName for type {tn}: {qn}")
            seen.add(key)
        reqs = _REQUIRED_ATTRS.get(str(tn))
        if reqs:
            attrs = ent.get("attributes") or {}
            for rk in reqs:
                val = attrs.get(rk, "")
                if isinstance(val, str):
                    val = val.strip()
                if val == "" or val is None:
                    errors.append(f"entities[{i}] ({tn}): missing attributes.{rk}")
    hive_db_qns: set[str] = set()
    for ent in entities:
        if str(ent.get("typeName")) == "hive_db":
            hq = qualified_name_key(ent)
            if hq:
                hive_db_qns.add(hq)
    for i, ent in enumerate(entities):
        if str(ent.get("typeName")) != "hive_table":
            continue
        rel = ent.get("relationshipAttributes") or {}
        db_block = rel.get("db")
        dq: str | None = None
        if isinstance(db_block, dict):
            ua = db_block.get("uniqueAttributes")
            if isinstance(ua, dict):
                q = ua.get("qualifiedName")
                dq = q.strip() if isinstance(q, str) and q.strip() else None
        if not dq:
            errors.append(
                f"entities[{i}] (hive_table): missing relationshipAttributes.db.uniqueAttributes.qualifiedName"
            )
            continue
        if dq not in hive_db_qns:
            errors.append(
                f"entities[{i}] (hive_table): relationshipAttributes.db references unknown hive_db qualifiedName="
                f"{dq} (declare hive_db in same file)",
            )
    return errors


def build_entity_body(ent: dict[str, Any]) -> dict[str, Any]:
    body: dict[str, Any] = {
        "typeName": ent["typeName"],
        "attributes": dict(ent.get("attributes") or {}),
    }
    if ent.get("relationshipAttributes"):
        body["relationshipAttributes"] = ent["relationshipAttributes"]
    return body


def main() -> None:
    p = argparse.ArgumentParser(description="Publish Atlas entities from YAML payloads.")
    p.add_argument(
        "--atlas-base-url",
        default="http://localhost:8090/atlas",
        help="From host with ingress: http://HOST:PORT/atlas ; from Compose on same network: http://atlas_server:21000",
    )
    p.add_argument("--user", default="admin")
    p.add_argument("--password", default="admin")
    p.add_argument(
        "--skip-existing",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="If entity with same typeName+qualifiedName exists, skip POST (idempotent).",
    )
    p.add_argument("config", type=Path, help="YAML with key 'entities' or legacy 'process' block")
    args = p.parse_args()
    entities = load_entities_from_yaml(args.config)
    errors = validate_entities(entities)
    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        raise SystemExit(2)
    for ent in entities:
        body = build_entity_body(ent)
        qn = qualified_name_key(ent)
        typ = str(ent.get("typeName") or "")
        if args.skip_existing and qn:
            guid = get_entity_guid_by_qualified_name(
                args.atlas_base_url, args.user, args.password, typ, qn
            )
            if guid:
                print(f"SKIP existing {typ} {qn} guid={guid}")
                continue
        code, text = post_entity(args.atlas_base_url, args.user, args.password, body)
        print(f"{code}: {text[:500]}")
        if code >= 400:
            sys.exit(1)


if __name__ == "__main__":
    main()
