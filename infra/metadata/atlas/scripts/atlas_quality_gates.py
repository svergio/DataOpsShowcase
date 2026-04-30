#!/usr/bin/env python3

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

_BASIC_SEARCH_LIMIT = 1000
try:
    _BASIC_SEARCH_LIMIT = max(50, min(10_000, int(os.environ.get("ATLAS_BASIC_SEARCH_PAGE_SIZE", "1000"))))
except ValueError:
    _BASIC_SEARCH_LIMIT = 1000


def auth_header_basic(user: str, password: str) -> str:
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return f"Basic {token}"


def post_json(base_url: str, user: str, password: str, path: str, body: dict[str, Any]) -> tuple[int, Any]:
    cleaned = base_url.rstrip("/")
    normalized = path if path.startswith("/") else f"/{path}"
    url = cleaned + normalized
    payload = json.dumps(body).encode()
    headers = {"Content-Type": "application/json", "Authorization": auth_header_basic(user, password)}
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw.strip() else None
    except urllib.error.HTTPError as err:
        raw = err.read().decode(errors="replace")
        try:
            return err.code, json.loads(raw) if raw.strip() else None
        except json.JSONDecodeError:
            return err.code, None


def _normalize_entities_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get("entities") or []
    out: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, dict) and isinstance(item.get("entity"), dict):
            out.append(dict(item["entity"]))
        elif isinstance(item, dict):
            out.append(item)
    return out


def post_json_search_basic(
    base_url: str,
    user: str,
    password: str,
    entity_type: str,
    *,
    limit: int,
    offset: int,
) -> tuple[int, dict[str, Any] | None]:
    body: dict[str, Any] = {
        "typeName": entity_type,
        "limit": limit,
        "offset": offset,
    }
    return post_json(base_url, user, password, "/api/atlas/v2/search/basic", body)


def push_pushgateway_plaintext(pg_url: str, job: str, instance: str, body: str) -> None:
    enc = urllib.parse.quote(instance, safe="")
    url = pg_url.rstrip("/") + f"/metrics/job/{job}/instance/{enc}"
    req = urllib.request.Request(
        url,
        data=body.encode("utf-8"),
        headers={"Content-Type": "text/plain; version=0.0.4"},
        method="PUT",
    )
    urllib.request.urlopen(req, timeout=15).read()


def search_basic_entities(base_url: str, user: str, password: str, entity_type: str) -> list[dict[str, Any]]:
    code, payload = post_json_search_basic(
        base_url, user, password, entity_type, limit=_BASIC_SEARCH_LIMIT, offset=0
    )
    if code >= 400 or not isinstance(payload, dict):
        raise RuntimeError(f"search/basic failed ({code}) for {entity_type}")
    return _normalize_entities_from_payload(payload)


def search_basic_count(base_url: str, user: str, password: str, entity_type: str) -> int:
    lim = _BASIC_SEARCH_LIMIT
    code, payload = post_json_search_basic(base_url, user, password, entity_type, limit=lim, offset=0)
    if code >= 400 or payload is None or not isinstance(payload, dict):
        return -1
    appr = payload.get("approximateCount")
    if isinstance(appr, int) and appr >= 0:
        return appr
    page = _normalize_entities_from_payload(payload)
    total = len(page)
    if len(page) < lim:
        return total
    offset = lim
    while True:
        code, payload = post_json_search_basic(base_url, user, password, entity_type, limit=lim, offset=offset)
        if code >= 400 or payload is None or not isinstance(payload, dict):
            return total
        chunk = _normalize_entities_from_payload(payload)
        total += len(chunk)
        if len(chunk) < lim:
            break
        offset += lim
    return total


def search_basic_process_qualname_matches(
    base_url: str,
    user: str,
    password: str,
    *,
    predicate: Callable[[str], bool],
    page_size: int | None = None,
) -> bool:
    lim = page_size or _BASIC_SEARCH_LIMIT
    offset = 0
    while True:
        code, payload = post_json_search_basic(
            base_url, user, password, "Process", limit=lim, offset=offset
        )
        if code >= 400 or payload is None or not isinstance(payload, dict):
            return False
        chunk = _normalize_entities_from_payload(payload)
        if not chunk:
            return False
        for ent in chunk:
            attrs = ent.get("attributes") or {}
            qn = str(attrs.get("qualifiedName", "") or "")
            if predicate(qn):
                return True
        if len(chunk) < lim:
            return False
        offset += lim


def _build_exposition(
    *,
    counts: dict[str, int],
    coarse_total: int,
    gate_pass: bool,
) -> str:
    lines = [
        "# HELP dataops_atlas_entity_count Estimated entity totals by coarse Atlas type.",
        "# TYPE dataops_atlas_entity_count gauge",
        "# HELP dataops_atlas_coarse_total Sum of coarse type counts.",
        "# TYPE dataops_atlas_coarse_total gauge",
        "# HELP dataops_atlas_gate_ok 1 if quality thresholds passed.",
        "# TYPE dataops_atlas_gate_ok gauge",
        "# HELP dataops_atlas_gate_fail 1 if quality thresholds failed.",
        "# TYPE dataops_atlas_gate_fail gauge",
        "# HELP dataops_atlas_last_quality_unixtime Seconds since unix epoch after last measurement.",
        "# TYPE dataops_atlas_last_quality_unixtime gauge",
    ]
    for k, v in counts.items():
        kl = str(k).replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'dataops_atlas_entity_count{{type="{kl}"}} {max(-1, int(v))}')
    gp = 1 if gate_pass else 0
    lines.append(f"dataops_atlas_coarse_total {max(0, int(coarse_total))}")
    lines.append(f"dataops_atlas_gate_ok {gp}")
    lines.append(f"dataops_atlas_gate_fail {1 - gp}")
    lines.append(f"dataops_atlas_last_quality_unixtime {int(time.time())}")
    return "\n".join(lines) + "\n"


def main() -> None:
    script_dir = Path(__file__).resolve().parent
    sys.path.insert(0, str(script_dir))

    parser = argparse.ArgumentParser(description="Atlas catalog quality gates and Pushgateway exposition.")
    parser.add_argument(
        "--atlas-base-url",
        default=os.environ.get("ATLAS_REST_URL") or "",
    )
    parser.add_argument("--user", default=os.environ.get("ATLAS_USER", "admin"))
    parser.add_argument("--password", default=os.environ.get("ATLAS_PASSWORD", "admin"))
    parser.add_argument("--min-any-total", type=int, default=3)
    parser.add_argument(
        "--duplicate-check-yaml",
        type=Path,
        nargs="?",
        default=None,
    )
    parser.add_argument(
        "--require-spark-kafka-presence",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    parser.add_argument(
        "--pushgateway-url",
        default=os.environ.get("PROMETHEUS_PUSHGATEWAY_URL", "").strip(),
    )
    parser.add_argument("--push-job", default=os.environ.get("ATLAS_PUSH_JOB", "atlas_quality"))
    parser.add_argument("--push-instance", default=os.environ.get("ATLAS_PUSH_INSTANCE", "dataops"))
    args = parser.parse_args()

    base_url = (
        args.atlas_base_url.strip().rstrip("/") if args.atlas_base_url.strip() else "http://atlas_server:21000"
    )

    fail_msgs: list[str] = []

    if args.duplicate_check_yaml is not None and args.duplicate_check_yaml.is_file():
        from entity_publish import load_entities_from_yaml  # pylint: disable=import-error
        from entity_publish import validate_entities as _validate  # pylint: disable=import-error

        ents = load_entities_from_yaml(args.duplicate_check_yaml)
        errs = _validate(ents)
        fail_msgs.extend(errs)

    coarse_types = ["Process", "kafka_topic", "hive_db", "hive_table"]
    counts: dict[str, int] = {}
    coarse_total = 0
    for tn in coarse_types:
        c = search_basic_count(base_url, args.user, args.password, tn)
        counts[tn] = c
        if c >= 0:
            coarse_total += c

    print("counts_by_type:", counts, "approx_sum=", coarse_total)
    if coarse_total < args.min_any_total:
        fail_msgs.append(f"summed counts {coarse_total} below --min-any-total {args.min_any_total}")

    if args.require_spark_kafka_presence:
        kc = counts.get("kafka_topic", -1)
        spark_seen = search_basic_process_qualname_matches(
            base_url,
            args.user,
            args.password,
            predicate=lambda qn: qn.startswith("spark://"),
        )
        if kc <= 0 or not spark_seen:
            fail_msgs.append("spark/kafka presence requirement not satisfied")

    gate_pass = len(fail_msgs) == 0
    exposition = _build_exposition(counts=counts, coarse_total=coarse_total, gate_pass=gate_pass)

    pg = args.pushgateway_url.strip()
    if pg:
        try:
            push_pushgateway_plaintext(pg, args.push_job, args.push_instance, exposition)
            print(f"pushed_metrics job={args.push_job} instance={args.push_instance}")
        except urllib.error.HTTPError as exc:
            print(f"WARN pushgateway HTTP {exc.code}", file=sys.stderr)
        except OSError as exc:
            print(f"WARN pushgateway error: {exc}", file=sys.stderr)

    if not gate_pass:
        for msg in fail_msgs:
            print(msg, file=sys.stderr)
        raise SystemExit(1)
    print("OK")


if __name__ == "__main__":
    main()
