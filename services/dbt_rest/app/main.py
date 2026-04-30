from __future__ import annotations

import json
import os
import subprocess
import threading
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response

from app import db

REST_TOKEN = (os.environ.get("DBT_REST_TOKEN") or "").strip()
DBT_HOME = os.environ.get("DBT_PROJECT_DIR", "/workspace/dbt")
PROFILES_DIR = os.environ.get("DBT_PROFILES_DIR", DBT_HOME)

WEB_TARGETS = frozenset({"staging", "vault", "marts"})
_ARTIFACT_NAMES = frozenset({"manifest.json", "catalog.json", "run_results.json", "graph.js"})


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.ensure_schema()
    yield


app = FastAPI(lifespan=lifespan)


def _require_run_uuid(run_id: str) -> str:
    try:
        return str(uuid.UUID(run_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid run_id") from exc


def _auth(authorization: str | None) -> None:
    if not REST_TOKEN:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    if authorization.removeprefix("Bearer ").strip() != REST_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")


async def _read_json_body(request: Request, *, allow_empty: bool) -> dict[str, Any]:
    raw = await request.body()
    if not raw or not raw.strip():
        if allow_empty:
            return {}
        raise HTTPException(status_code=400, detail="JSON body required")
    try:
        val = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="invalid JSON body") from exc
    if not isinstance(val, dict):
        raise HTTPException(status_code=400, detail="JSON object required")
    return val


def _with_run_target_path(argv: list[str], run_id: str) -> list[str]:
    rel = f"target/runs/{run_id}"
    if not argv or argv[0] != "dbt":
        raise ValueError("argv must start with dbt")
    return ["dbt", "--target-path", rel, *argv[1:]]


def _argv_from_airflow_body(body: dict[str, Any]) -> list[str]:
    target = str(body.get("target") or "dwh").strip() or "dwh"
    cmd = str(body.get("command") or "").strip()
    if cmd:
        return ["dbt", *cmd.split(), "--target", target]
    selectors = body.get("selectors") or []
    if not isinstance(selectors, list):
        raise HTTPException(status_code=400, detail="selectors must be a list")
    if not selectors:
        raise HTTPException(
            status_code=400,
            detail="non-empty selectors or command is required for POST /runs",
        )
    sel = " ".join(str(s) for s in selectors)
    fail_on_test = bool(body.get("fail_on_test_failure", True))
    cmd_prefix = ["dbt", "build", "--select", sel, "--target", target]
    if not fail_on_test:
        cmd_prefix.append("--no-fail-fast")
    return cmd_prefix


def _argv_from_web_job(layer: str, body: dict[str, Any]) -> list[str]:
    dbt_target = "dwh"
    selectors = body.get("selectors") or []
    if not isinstance(selectors, list):
        raise HTTPException(status_code=400, detail="selectors must be a list")
    if not selectors:
        selectors = [f"tag:{layer}"]
    sel = " ".join(str(s) for s in selectors)
    fail_on_test = bool(body.get("fail_on_test_failure", True))
    cmd: list[str] = ["dbt", "build", "--select", sel, "--target", dbt_target]
    if not fail_on_test:
        cmd.append("--no-fail-fast")
    if body.get("full_refresh"):
        cmd.append("--full-refresh")
    if body.get("defer"):
        cmd.append("--defer")
    vars_d = body.get("vars") or {}
    if vars_d:
        if not isinstance(vars_d, dict):
            raise HTTPException(status_code=400, detail="vars must be an object")
        cmd.extend(["--vars", json.dumps(vars_d)])
    return cmd


def _parse_iso_duration(started_at: str | None, finished_at: str | None) -> float | None:
    if not started_at or not finished_at:
        return None
    try:
        a = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        b = datetime.fromisoformat(finished_at.replace("Z", "+00:00"))
        return max(0.0, (b - a).total_seconds())
    except ValueError:
        return None


def _load_artifacts_from_disk(run_id: str) -> tuple[dict[str, bytes], list[str]]:
    base = os.path.join(DBT_HOME, "target", "runs", run_id)
    found: dict[str, bytes] = {}
    names: list[str] = []
    for name in ("manifest.json", "catalog.json", "run_results.json", "graph.js"):
        path = os.path.join(base, name)
        if os.path.isfile(path):
            with open(path, "rb") as f:
                found[name] = f.read()
            names.append(name)
    return found, names


def _worker(run_id: str, argv: list[str], env: dict[str, str]) -> None:
    argv_tp = _with_run_target_path(argv, run_id)
    run_dir = os.path.join(DBT_HOME, "target", "runs", run_id)
    os.makedirs(run_dir, exist_ok=True)
    log_chunks: list[str] = []
    started_iso = ""
    try:
        started_iso = db.mark_running(run_id)
    except Exception as exc:  # noqa: BLE001
        log_chunks.append(str(exc))
        finished = datetime.now(timezone.utc).isoformat()
        db.mark_finished_best_effort(
            run_id,
            status="error",
            finished_iso=finished,
            duration_sec=None,
            logs="".join(log_chunks),
            artifact_names=[],
        )
        return
    status = "error"
    try:
        proc = subprocess.run(
            argv_tp,
            cwd=DBT_HOME,
            env=env,
            capture_output=True,
            text=True,
            timeout=7200,
        )
        out = (proc.stdout or "") + ((proc.stderr or "") and f"\n{proc.stderr}" or "")
        log_chunks.append(out)
        status = "success" if proc.returncode == 0 else "failed"
    except subprocess.TimeoutExpired as exc:
        tail = (exc.stdout or "") + ((exc.stderr or "") and f"\n{exc.stderr}" or "")
        log_chunks.append(tail or "timeout")
        status = "timeout"
    except Exception as exc:  # noqa: BLE001
        log_chunks.append(str(exc))
        status = "error"
    finished = datetime.now(timezone.utc).isoformat()
    log_text = "".join(log_chunks)
    _, names = _load_artifacts_from_disk(run_id)
    dur = _parse_iso_duration(started_iso, finished)
    db.mark_finished_best_effort(
        run_id,
        status=status,
        finished_iso=finished,
        duration_sec=dur,
        logs=log_text,
        artifact_names=names,
    )


def _start_run(
    *,
    argv: list[str],
    job_name: str | None,
    web_target: str | None,
    authorization: str | None,
) -> dict[str, str]:
    _auth(authorization)
    run_id = str(uuid.uuid4())
    db.insert_queued(run_id, job_name, web_target)
    env = os.environ.copy()
    env.setdefault("DBT_PROFILES_DIR", PROFILES_DIR)
    thread = threading.Thread(target=_worker, args=(run_id, argv, env), daemon=True)
    thread.start()
    return {"run_id": run_id}


def _run_view(run_id: str) -> dict[str, Any]:
    run_id = _require_run_uuid(run_id)
    data = db.get_run(run_id)
    if not data:
        raise HTTPException(status_code=404, detail="run not found")
    status = str(data.get("status") or "").lower()
    ds = data.get("duration_sec")
    if ds is not None:
        ds = float(ds)
    return {
        "run_id": data["run_id"],
        "status": status,
        "started_at": data.get("started_at"),
        "finished_at": data.get("finished_at"),
        "artifacts_url": None,
        "duration_sec": ds,
        "job_name": data.get("job_name"),
        "artifacts": list(data.get("artifacts") or []),
    }


@app.get("/health")
def health():
    if not db.DSN:
        return JSONResponse(
            {"status": "degraded", "database": "DBT_REST_DB_DSN not set"},
            status_code=503,
        )
    if not db.ping():
        return JSONResponse(
            {"status": "unhealthy", "database": "unavailable"},
            status_code=503,
        )
    return {"status": "ok", "database": "ok"}


@app.post("/runs")
async def create_run_airflow(
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict[str, str]:
    body = await _read_json_body(request, allow_empty=False)
    argv = _argv_from_airflow_body(body)
    job = body.get("job")
    job_name = str(job) if job is not None else None
    return _start_run(argv=argv, job_name=job_name, web_target=None, authorization=authorization)


@app.post("/jobs/run/{layer}")
async def create_run_web(
    layer: str,
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    if layer not in WEB_TARGETS:
        raise HTTPException(status_code=400, detail="invalid target")
    body = await _read_json_body(request, allow_empty=True)
    argv = _argv_from_web_job(layer, body)
    rid = _start_run(
        argv=argv,
        job_name=f"web_{layer}",
        web_target=layer,
        authorization=authorization,
    )
    return {
        "run_id": rid["run_id"],
        "status": "queued",
        "target": layer,
    }


@app.get("/runs/{run_id}")
def get_run_airflow(
    run_id: str,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    _auth(authorization)
    return _run_view(run_id)


@app.get("/runs/{run_id}/status")
def get_run_status_web(
    run_id: str,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    _auth(authorization)
    return _run_view(run_id)


@app.get("/runs/{run_id}/logs")
def get_logs(
    run_id: str,
    authorization: str | None = Header(default=None),
) -> PlainTextResponse:
    _auth(authorization)
    run_id = _require_run_uuid(run_id)
    text = db.get_logs(run_id)
    if text is None:
        raise HTTPException(status_code=404, detail="run not found")
    return PlainTextResponse(content=text, status_code=200)


@app.get("/artifacts/{run_id}/{name}")
def get_artifact(
    run_id: str,
    name: str,
    authorization: str | None = Header(default=None),
) -> Response:
    _auth(authorization)
    run_id = _require_run_uuid(run_id)
    if name not in _ARTIFACT_NAMES:
        raise HTTPException(status_code=400, detail="invalid artifact name")
    if not db.run_exists(run_id):
        raise HTTPException(status_code=404, detail="run not found")
    files, _ = _load_artifacts_from_disk(run_id)
    blob = files.get(name)
    if blob is None:
        raise HTTPException(status_code=404, detail="artifact not found")
    ctype = "application/json"
    if name == "graph.js":
        ctype = "application/javascript"
    return Response(content=blob, media_type=ctype)
