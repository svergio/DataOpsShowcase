#!/usr/bin/env python3
"""Print latest DagRun state per DAG via Airflow REST API (v1)."""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


def _auth_header(user: str, password: str) -> str:
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return f"Basic {token}"


def _get_json(url: str, auth: str, timeout: float) -> dict:
    req = urllib.request.Request(url)
    req.add_header("Authorization", auth)
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        raise RuntimeError(f"HTTP {exc.code} {url}: {body}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON array",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="HTTP timeout seconds (default: 60)",
    )
    args = parser.parse_args()

    base = os.environ.get("AIRFLOW_API_BASE_URL", "http://127.0.0.1:8080/airflow/api/v1").rstrip("/")
    user = os.environ.get("AIRFLOW_ADMIN_USER", "admin")
    password = os.environ.get("AIRFLOW_ADMIN_PASSWORD", "admin")
    auth = _auth_header(user, password)

    dags_url = f"{base}/dags?limit=200"
    data = _get_json(dags_url, auth, args.timeout)
    dags = data.get("dags") or []
    dag_ids = sorted(d["dag_id"] for d in dags if d.get("dag_id"))

    rows: list[dict[str, str | None]] = []
    for dag_id in dag_ids:
        q = urllib.parse.urlencode(
            {"limit": "1", "order_by": "-execution_date"},
        )
        runs_url = f"{base}/dags/{urllib.parse.quote(dag_id, safe='')}/dagRuns?{q}"
        try:
            runs_payload = _get_json(runs_url, auth, args.timeout)
        except RuntimeError as exc:
            rows.append(
                {
                    "dag_id": dag_id,
                    "state": "error",
                    "logical_date": None,
                    "detail": str(exc),
                },
            )
            continue
        run_list = runs_payload.get("dag_runs") or []
        if not run_list:
            rows.append(
                {"dag_id": dag_id, "state": None, "logical_date": None, "detail": None},
            )
            continue
        run = run_list[0]
        rows.append(
            {
                "dag_id": dag_id,
                "state": run.get("state"),
                "logical_date": run.get("logical_date") or run.get("execution_date"),
                "detail": None,
            },
        )

    if args.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return 0

    w_id = max(len(r["dag_id"]) for r in rows) if rows else 10
    w_st = max(len((r["state"] or "-")[:20]) for r in rows) if rows else 5
    for r in rows:
        did = r["dag_id"]
        st = r["state"] or "-"
        ld = r["logical_date"] or "-"
        extra = f" ({r['detail']})" if r.get("detail") else ""
        print(f"{did:{w_id}}  {st:{w_st}}  {ld}{extra}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as e:
        print(e, file=sys.stderr)
        raise SystemExit(1)
