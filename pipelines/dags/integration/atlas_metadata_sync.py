from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from airflow.decorators import dag
from airflow.operators.python import PythonOperator

_AIRFLOW_HOME = Path(os.environ.get("AIRFLOW_HOME", "/opt/airflow"))
_ATLAS_ROOT = _AIRFLOW_HOME / "infra" / "metadata" / "atlas"
_SCRIPTS_DIR = _ATLAS_ROOT / "scripts"
_INGEST_DIR = _ATLAS_ROOT / "ingestion"


def _merge_int(primary: Any, secondary: Any, default: int, *, minimum: int = 1) -> int:
    for candidate in (primary, secondary):
        if candidate is None:
            continue
        if isinstance(candidate, str) and not candidate.strip():
            continue
        try:
            return max(minimum, int(candidate))
        except (TypeError, ValueError):
            continue
    return max(minimum, default)


def _merge_float(primary: Any, secondary: Any, default: float, *, minimum: float = 0.0) -> float:
    for candidate in (primary, secondary):
        if candidate is None:
            continue
        if isinstance(candidate, str) and not candidate.strip():
            continue
        try:
            return max(minimum, float(candidate))
        except (TypeError, ValueError):
            continue
    return max(minimum, default)


def _skip_static_kafka(conf: dict[str, Any]) -> bool:
    if conf.get("skip_static_kafka") is True:
        return True
    v = conf.get("skip_static_kafka")
    if isinstance(v, str) and v.strip().lower() in ("1", "true", "yes"):
        return True
    ev = os.environ.get("ATLAS_SKIP_STATIC_KAFKA", "").strip().lower()
    return ev in ("1", "true", "yes")


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.setdefault("PYTHONNOUSERSITE", "1")
    return subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)


def _run_retry(cmd: list[str], *, retries: int, delay_sec: float) -> None:
    last: subprocess.CompletedProcess[str] | None = None
    for attempt in range(max(1, retries)):
        out = _run(cmd)
        if out.stdout:
            print(out.stdout)
        if out.stderr:
            print(out.stderr, file=sys.stderr)
        if out.returncode == 0:
            return
        last = out
        print(f"retry {attempt + 1}/{retries} rc={out.returncode}", file=sys.stderr)
        if attempt + 1 < retries:
            time.sleep(delay_sec)
    raise subprocess.CalledProcessError(
        last.returncode if last else 1,
        cmd,
        output=last.stdout if last else None,
        stderr=last.stderr if last else None,
    )


def _publish(
    python_exe: Path,
    atlas_url: str,
    path: Path,
    *,
    retries: int,
    delay_sec: float,
) -> None:
    _run_retry(
        [
            str(python_exe.resolve()),
            str(_SCRIPTS_DIR / "entity_publish.py"),
            "--atlas-base-url",
            atlas_url,
            str(path.resolve()),
        ],
        retries=retries,
        delay_sec=delay_sec,
    )


def atlas_sync_callable(**kwargs) -> None:
    dag_run = kwargs.get("dag_run")
    conf: dict[str, Any] = (dag_run.conf or {}) if dag_run else {}
    mode = conf.get("mode", "full")
    retries = _merge_int(conf.get("publish_retries"), os.environ.get("ATLAS_PUBLISH_RETRIES"), 3)
    delay_sec = _merge_float(conf.get("publish_retry_delay_sec"), os.environ.get("ATLAS_PUBLISH_RETRY_DELAY_SEC"), 5.0)
    ql_retries = _merge_int(conf.get("quality_retries"), os.environ.get("ATLAS_QUALITY_RETRIES"), 2)
    ql_delay_sec = _merge_float(conf.get("quality_retry_delay_sec"), os.environ.get("ATLAS_QUALITY_RETRY_DELAY_SEC"), 15.0)
    python_exe = Path(sys.executable)
    atlas_url = (
        os.environ.get("ATLAS_REST_URL", "").strip().rstrip("/") or "http://atlas_server:21000"
    )
    mode_label = "lite_incremental" if mode == "incremental" else "full"
    report_lines: list[str] = []

    def step(name: str) -> None:
        report_lines.append(f"stage:start:{name}")

    if mode != "incremental":
        step("reflect_postgres_hive")
        dsn = os.environ.get("PG_REFLECT_DSN", "").strip()
        if not dsn:
            raise RuntimeError(
                "PG_REFLECT_DSN is required on the Airflow worker for Postgres reflection (Compose sets it).",
            )
        pg_out = Path("/tmp/atlas_pg_reflect.yml")
        _run_retry(
            [
                str(python_exe),
                str(_SCRIPTS_DIR / "postgres_reflect_to_yaml.py"),
                "--dsn",
                dsn,
                "--emit-entities",
                "hive",
                "--output",
                str(pg_out),
            ],
            retries=retries,
            delay_sec=delay_sec,
        )
        _publish(python_exe, atlas_url, pg_out, retries=retries, delay_sec=delay_sec)

        step("dbt_manifest")
        man = Path("/workspace/dbt/target/manifest.json")
        if man.is_file():
            dbt_out = Path("/tmp/atlas_dbt_models.yml")
            _run_retry(
                [
                    str(python_exe),
                    str(_SCRIPTS_DIR / "dbt_manifest_to_atlas_yaml.py"),
                    "--manifest",
                    str(man),
                    "--output",
                    str(dbt_out),
                ],
                retries=retries,
                delay_sec=delay_sec,
            )
            _publish(python_exe, atlas_url, dbt_out, retries=retries, delay_sec=delay_sec)

        step("generators_inventory_yaml")
        gen_cfg = Path(
            os.environ.get("GENERATOR_CONFIG_JSON", "/opt/airflow/configs/generators/company.generator.json")
        )
        gen_out = Path("/tmp/atlas_generators_inventory.yml")
        if gen_cfg.is_file():
            _run_retry(
                [
                    str(python_exe),
                    str(_SCRIPTS_DIR / "generators_inventory_to_atlas_yaml.py"),
                    "--config",
                    str(gen_cfg),
                    "--output",
                    str(gen_out),
                ],
                retries=retries,
                delay_sec=delay_sec,
            )
            _publish(python_exe, atlas_url, gen_out, retries=retries, delay_sec=delay_sec)

    static_order = (
        _INGEST_DIR / "postgres_oltp.yml",
        _INGEST_DIR / "postgres_olap.yml",
        _INGEST_DIR / "postgres_metadb.yml",
        _INGEST_DIR / "kafka_topics_batch.yml",
        _INGEST_DIR / "kafka_cdc_topics.yml",
        _INGEST_DIR / "debezium_connectors.yml",
        _INGEST_DIR / "minio_buckets.yml",
        _INGEST_DIR / "spark_cdc_lineage.yml",
        _INGEST_DIR / "superset_lineage.yml",
    )
    sk = _skip_static_kafka(conf)
    if sk:
        skip_names = {"kafka_topics_batch.yml", "kafka_cdc_topics.yml"}
        static_order = tuple(f for f in static_order if f.name not in skip_names)
        step("note_skip_static_kafka_yml")
    for f in static_order:
        step(f"publish_{f.name}")
        if f.is_file():
            _publish(python_exe, atlas_url, f, retries=retries, delay_sec=delay_sec)

    step("atlas_quality_gates")
    _run_retry(
        [
            str(python_exe),
            str(_SCRIPTS_DIR / "atlas_quality_gates.py"),
            "--atlas-base-url",
            atlas_url,
            "--min-any-total",
            os.environ.get("ATLAS_QUALITY_MIN_TOTAL", "5"),
        ],
        retries=ql_retries,
        delay_sec=ql_delay_sec,
    )

    print("atlas_metadata_sync_report:")
    for ln in report_lines:
        print(ln)
    print(f"stage:end:ok mode={mode_label}")


@dag(
    dag_id="atlas_metadata_sync",
    schedule="0 */6 * * *",
    start_date=datetime(2025, 1, 1),
    tags=["integration", "metadata", "atlas"],
    catchup=False,
)
def atlas_metadata_sync():
    PythonOperator(task_id="reflect_publish_verify", python_callable=atlas_sync_callable)


dag = atlas_metadata_sync()
