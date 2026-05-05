from __future__ import annotations

import os
from datetime import timedelta
from typing import Any

from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator

from services.common.config_loader import load_yaml


def _comma_py_files(paths: list[str]) -> str:
    return ",".join(paths)


def build_spark_submit_operator(
    *,
    job_id: str,
    task_id: str,
    application_args: list[str],
    env_vars: dict[str, str] | None = None,
    **overrides: Any,
) -> SparkSubmitOperator:
    cfg_root = load_yaml("spark_jobs")
    defaults = cfg_root.get("defaults", {}) or {}
    jobs = cfg_root.get("jobs", {}) or {}
    if job_id not in jobs:
        raise ValueError(f"spark job not configured: {job_id}")

    job_cfg = jobs[job_id]
    privacy = cfg_root.get("privacy", {}) or {}
    salt_env = str(privacy.get("salt_env", "SPARK_PRIVACY_SALT"))

    py_paths = list(job_cfg.get("py_files") or [])
    if not py_paths:
        raise ValueError(f"spark_jobs.yaml jobs.{job_id}.py_files is required")

    conf = dict(overrides.pop("conf", {}) or {})
    pkg = defaults.get("java_package", "org.postgresql:postgresql:42.7.3")
    conf.setdefault("spark.jars.packages", pkg)

    merged_env: dict[str, str] = {}
    jdbc_url = os.environ.get("DWH_JDBC_URL", "")
    if jdbc_url:
        merged_env["DWH_JDBC_URL"] = jdbc_url
    if os.environ.get(salt_env):
        merged_env[salt_env] = os.environ[salt_env]
    merged_env["SPARK_JOB_ENV"] = os.environ.get("SPARK_JOB_ENV", str(privacy.get("env_arg", "production")))
    if env_vars:
        merged_env.update(env_vars)

    retry_min = int(job_cfg.get("retry_delay_minutes", defaults.get("retry_delay_minutes", 5)))
    op_kwargs: dict[str, Any] = {
        "task_id": task_id,
        "application": job_cfg["application"],
        "py_files": _comma_py_files(py_paths),
        "conn_id": str(job_cfg.get("conn_id", defaults.get("conn_id", "spark_default"))),
        "name": str(job_cfg.get("name", task_id)),
        "verbose": bool(job_cfg.get("verbose", defaults.get("verbose", False))),
        "application_args": application_args,
        "env_vars": merged_env,
        "conf": conf,
        "retries": int(job_cfg.get("retries", 3)),
        "retry_delay": timedelta(minutes=retry_min),
        "executor_cores": int(job_cfg.get("executor_cores", 2)),
        "executor_memory": str(job_cfg.get("executor_memory", "1g")),
        "driver_memory": str(job_cfg.get("driver_memory", "1g")),
        "num_executors": int(job_cfg.get("num_executors", 1)),
    }
    op_kwargs.update(overrides)
    return SparkSubmitOperator(**op_kwargs)
