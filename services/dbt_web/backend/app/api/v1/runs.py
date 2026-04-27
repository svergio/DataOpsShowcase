from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request

from app.schemas.contracts import RunJobRequest, RunJobResponse, RunLogsResponse, RunStatusResponse, TargetName
from app.state import AppState

router = APIRouter()


def get_state(request: Request) -> AppState:
    return request.app.state.ctx


@router.post("/runs/{target}", response_model=RunJobResponse)
def run_job(target: TargetName, payload: RunJobRequest, request: Request) -> RunJobResponse:
    return get_state(request).dbt_rest.run_job(target, payload)


@router.get("/runs/{run_id}", response_model=RunStatusResponse)
def run_status(run_id: str, request: Request) -> RunStatusResponse:
    return get_state(request).dbt_rest.get_run_status(run_id)


@router.get("/runs/{run_id}/logs", response_model=RunLogsResponse)
def run_logs(run_id: str, request: Request) -> RunLogsResponse:
    return get_state(request).dbt_rest.get_run_logs(run_id)


@router.get("/runs")
def list_runs(
    request: Request,
    status: str | None = Query(default=None),
    target: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
) -> dict:
    """Aggregate latest run summaries per target from MinIO artifacts."""
    state = get_state(request)
    targets = [target] if target else ["staging", "vault", "marts"]
    items: list[dict[str, Any]] = []
    for tgt in targets:
        latest = state.storage.get_json(f"dbt-artifacts/latest-success/{tgt}/run_results.json") or {}
        meta = latest.get("metadata", {}) or {}
        results = latest.get("results", []) or []
        passed = sum(1 for r in results if r.get("status") in {"pass", "success"})
        failed = len(results) - passed
        run_status = "success" if failed == 0 and results else ("failed" if failed > 0 else "unknown")
        if status and status != run_status:
            continue
        items.append(
            {
                "target": tgt,
                "run_id": meta.get("invocation_id"),
                "generated_at": meta.get("generated_at"),
                "dbt_version": meta.get("dbt_version"),
                "elapsed_time": latest.get("elapsed_time"),
                "results_total": len(results),
                "results_passed": passed,
                "results_failed": failed,
                "status": run_status,
            }
        )
    items = items[:limit]
    return {"total": len(items), "items": items}


@router.get("/tests/summary")
def tests_summary(
    request: Request,
    target: str | None = Query(default=None),
    severity: str | None = Query(default=None),
) -> dict:
    state = get_state(request)
    targets = [target] if target else ["staging", "vault", "marts"]
    failed: list[dict[str, Any]] = []
    summary: dict[str, dict[str, int]] = {}
    for tgt in targets:
        latest = state.storage.get_json(f"dbt-artifacts/latest-success/{tgt}/run_results.json") or {}
        results = latest.get("results", []) or []
        for r in results:
            unique_id = r.get("unique_id", "")
            if not unique_id.startswith("test."):
                continue
            sev = (r.get("config", {}) or {}).get("severity") or r.get("severity") or "error"
            status_str = r.get("status", "unknown")
            ok = status_str in {"pass", "success"}
            bucket = summary.setdefault(tgt, {"total": 0, "passed": 0, "failed": 0})
            bucket["total"] += 1
            if ok:
                bucket["passed"] += 1
            else:
                bucket["failed"] += 1
                if severity and severity != sev:
                    continue
                failed.append(
                    {
                        "target": tgt,
                        "unique_id": unique_id,
                        "status": status_str,
                        "severity": sev,
                        "message": r.get("message"),
                        "execution_time": r.get("execution_time"),
                    }
                )
    return {"summary": summary, "failed": failed, "failed_total": len(failed)}
