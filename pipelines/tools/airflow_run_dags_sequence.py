#!/usr/bin/env python3
"""Unpause DAGs, trigger in pipeline order, wait for terminal state (Airflow CLI)."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from typing import Literal

Terminal = Literal["success", "failed"]

DEFAULT_DAGS: list[str] = [
    "dag_ingest_oltp_to_stg",
    "dag_ingest_kafka_orders_to_raw",
    "dag_ingest_kafka_payments_to_raw",
    "dag_ingest_minio_files_to_raw",
    "dag_ingest_kafka_extensions_to_raw",
    "dag_spark_preprocess_to_stg",
    "dag_load_datavault",
    "dag_scd2_satellites",
    "dag_dbt_staging_rest",
    "dag_dbt_vault_rest",
    "dag_dbt_marts_rest",
    "dag_dbt_dqc_rest",
    "dag_data_quality_checks",
    "dag_serving_optimizations",
    "dag_ml_train_spark",
]


def _airflow(*args: str) -> str:
    out = subprocess.check_output(["airflow", *args], text=True)
    return out


def _runs_json(dag_id: str) -> list[dict]:
    raw = _airflow("dags", "list-runs", "-d", dag_id, "--no-backfill", "-o", "json")
    return json.loads(raw)


def wait_run(dag_id: str, run_id: str, interval: float, max_wait: float) -> Terminal:
    deadline = time.monotonic() + max_wait
    while time.monotonic() < deadline:
        for row in _runs_json(dag_id):
            if row.get("run_id") == run_id:
                st = (row.get("state") or "").lower()
                if st == "success":
                    return "success"
                if st == "failed":
                    return "failed"
                break
        time.sleep(interval)
    raise TimeoutError(f"{dag_id} run {run_id} did not finish within {max_wait}s")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--interval",
        type=float,
        default=5.0,
        help="Poll interval seconds (default: 5)",
    )
    parser.add_argument(
        "--max-wait",
        type=float,
        default=3600.0,
        help="Max wait per DAG run in seconds (default: 3600)",
    )
    parser.add_argument(
        "--prefix",
        default="manual__e2e_seq",
        help="Run id prefix (default: manual__e2e_seq)",
    )
    parser.add_argument(
        "--skip",
        action="append",
        default=[],
        help="DAG id to skip (repeatable)",
    )
    args = parser.parse_args()
    skip = set(args.skip)
    results: list[tuple[str, str, str]] = []

    for dag_id in DEFAULT_DAGS:
        if dag_id in skip:
            print(f"skip {dag_id}", flush=True)
            continue
        _airflow("dags", "unpause", dag_id)
        run_id = f"{args.prefix}__{dag_id}__{int(time.time())}"
        _airflow("dags", "trigger", "-r", run_id, dag_id)
        print(f"triggered {dag_id} {run_id}", flush=True)
        try:
            final = wait_run(dag_id, run_id, args.interval, args.max_wait)
        except TimeoutError as exc:
            print(f"TIMEOUT {exc}", file=sys.stderr, flush=True)
            return 1
        results.append((dag_id, run_id, final))
        print(f"{dag_id} -> {final}", flush=True)
        if final != "success":
            return 1

    for dag_id, run_id, final in results:
        print(f"OK  {dag_id}  {run_id}  {final}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
