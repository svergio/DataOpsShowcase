from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

import psycopg
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)

DSN = (os.environ.get("DBT_REST_DB_DSN") or "").strip()
LOG_MAX_CHARS = int(os.environ.get("DBT_REST_LOG_MAX_CHARS", "1000000"))
FINISH_RETRIES = max(1, int(os.environ.get("DBT_REST_FINISH_RETRIES", "5")))
FINISH_RETRY_BASE_SEC = float(os.environ.get("DBT_REST_FINISH_RETRY_DELAY_SEC", "0.5"))


def _connect() -> psycopg.Connection:
    if not DSN:
        raise RuntimeError("DBT_REST_DB_DSN is not set")
    return psycopg.connect(DSN, autocommit=True)


def ping() -> bool:
    if not DSN:
        return False
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return True
    except Exception as exc:
        logger.warning("database ping failed: %s", exc)
        return False


def ensure_schema() -> None:
    stmts = [
        "CREATE SCHEMA IF NOT EXISTS dbt_rest",
        """
    CREATE TABLE IF NOT EXISTS dbt_rest.runs (
        run_id UUID PRIMARY KEY,
        status TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        started_at TIMESTAMPTZ,
        finished_at TIMESTAMPTZ,
        duration_sec DOUBLE PRECISION,
        job_name TEXT,
        web_target TEXT,
        logs TEXT,
        artifact_names JSONB NOT NULL DEFAULT '[]'::jsonb
    )
    """,
        """
    CREATE INDEX IF NOT EXISTS runs_status_created_idx
    ON dbt_rest.runs (status, created_at DESC)
    """,
    ]
    with _connect() as conn:
        with conn.cursor() as cur:
            for stmt in stmts:
                cur.execute(stmt)


def insert_queued(run_id: str, job_name: str | None, web_target: str | None) -> None:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO dbt_rest.runs (
                    run_id, status, job_name, web_target, logs, artifact_names
                ) VALUES (%s::uuid, %s, %s, %s, %s, %s::jsonb)
                """,
                (run_id, "queued", job_name, web_target, "", "[]"),
            )


def mark_running(run_id: str) -> str:
    started = datetime.now(timezone.utc)
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE dbt_rest.runs
                SET status = %s, started_at = %s, updated_at = NOW()
                WHERE run_id = %s::uuid
                """,
                ("running", started, run_id),
            )
    return started.isoformat()


def mark_finished(
    run_id: str,
    *,
    status: str,
    finished_iso: str,
    duration_sec: float | None,
    logs: str,
    artifact_names: list[str],
) -> None:
    log_text = logs if len(logs) <= LOG_MAX_CHARS else logs[: LOG_MAX_CHARS - 128] + "\n... [truncated]\n"
    finished_dt = datetime.fromisoformat(finished_iso.replace("Z", "+00:00"))
    payload = json.dumps(artifact_names)
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE dbt_rest.runs
                SET status = %s,
                    finished_at = %s,
                    duration_sec = %s,
                    logs = %s,
                    artifact_names = %s::jsonb,
                    updated_at = NOW()
                WHERE run_id = %s::uuid
                """,
                (status, finished_dt, duration_sec, log_text, payload, run_id),
            )


def force_terminal_persist(
    run_id: str,
    *,
    status: str,
    finished_iso: str,
    duration_sec: float | None,
    artifact_names: list[str],
    note: str,
) -> None:
    finished_dt = datetime.fromisoformat(finished_iso.replace("Z", "+00:00"))
    note_t = (
        note if len(note) <= LOG_MAX_CHARS else note[: LOG_MAX_CHARS - 128] + "\n... [truncated]\n"
    )
    payload = json.dumps(artifact_names)
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE dbt_rest.runs
                SET status = %s,
                    finished_at = %s,
                    duration_sec = COALESCE(%s, duration_sec),
                    logs = LEFT(COALESCE(logs, '') || E'\n\n' || %s, %s),
                    artifact_names = %s::jsonb,
                    updated_at = NOW()
                WHERE run_id = %s::uuid
                """,
                (status, finished_dt, duration_sec, note_t, LOG_MAX_CHARS, payload, run_id),
            )
            if cur.rowcount == 0:
                logger.error("force_terminal_persist: no row for run_id=%s", run_id)


def mark_finished_best_effort(
    run_id: str,
    *,
    status: str,
    finished_iso: str,
    duration_sec: float | None,
    logs: str,
    artifact_names: list[str],
) -> None:
    last_exc: Exception | None = None
    for attempt in range(FINISH_RETRIES):
        try:
            mark_finished(
                run_id,
                status=status,
                finished_iso=finished_iso,
                duration_sec=duration_sec,
                logs=logs,
                artifact_names=artifact_names,
            )
            return
        except Exception as exc:
            last_exc = exc
            if attempt + 1 < FINISH_RETRIES:
                delay = FINISH_RETRY_BASE_SEC * (2**attempt)
                logger.warning(
                    "mark_finished failed (attempt %s/%s), retry in %ss: %s",
                    attempt + 1,
                    FINISH_RETRIES,
                    delay,
                    exc,
                )
                time.sleep(delay)
            else:
                logger.error(
                    "mark_finished failed after %s attempts: %s",
                    FINISH_RETRIES,
                    exc,
                    exc_info=True,
                )
    fallback = (
        f"[dbt-rest] could not persist full row after {FINISH_RETRIES} attempts: {last_exc!r}\n"
        f"intended_status={status}\n"
        "--- log tail ---\n"
        f"{logs[-12000:]}"
    )
    try:
        force_terminal_persist(
            run_id,
            status=status,
            finished_iso=finished_iso,
            duration_sec=duration_sec,
            artifact_names=artifact_names,
            note=fallback,
        )
    except Exception as exc:
        logger.critical(
            "force_terminal_persist failed for run_id=%s; row may stay non-terminal: %s",
            run_id,
            exc,
            exc_info=True,
        )


def get_run(run_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT run_id, status, started_at, finished_at, duration_sec,
                       job_name, artifact_names
                FROM dbt_rest.runs WHERE run_id = %s::uuid
                """,
                (run_id,),
            )
            row = cur.fetchone()
    if not row:
        return None
    data = dict(row)
    data["run_id"] = str(data["run_id"])
    an = data.get("artifact_names")
    if isinstance(an, str):
        an = json.loads(an)
    data["artifacts"] = list(an) if an else []
    del data["artifact_names"]
    for k in ("started_at", "finished_at"):
        v = data.get(k)
        if isinstance(v, datetime):
            data[k] = v.isoformat()
    return data


def get_logs(run_id: str) -> str | None:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT logs FROM dbt_rest.runs WHERE run_id = %s::uuid",
                (run_id,),
            )
            row = cur.fetchone()
    if not row:
        return None
    return row[0] or ""


def run_exists(run_id: str) -> bool:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM dbt_rest.runs WHERE run_id = %s::uuid",
                (run_id,),
            )
            return cur.fetchone() is not None
