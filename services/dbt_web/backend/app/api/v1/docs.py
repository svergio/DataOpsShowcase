from __future__ import annotations

from fastapi import APIRouter, Request

from app.state import AppState
from app.services.validators import validate_manifest

router = APIRouter()


def get_state(request: Request) -> AppState:
    return request.app.state.ctx


def _latest(state: AppState, target: str, name: str) -> dict:
    return state.storage.get_json(f"dbt-artifacts/latest-success/{target}/{name}") or {}


@router.get("/docs/manifest")
def docs_manifest(request: Request) -> dict:
    return _latest(get_state(request), "marts", "manifest.json")


@router.get("/docs/catalog")
def docs_catalog(request: Request) -> dict:
    return _latest(get_state(request), "marts", "catalog.json")


@router.get("/docs/run_results")
def docs_run_results(request: Request) -> dict:
    return _latest(get_state(request), "marts", "run_results.json")


@router.get("/docs/graph")
def docs_graph(request: Request) -> dict:
    state = get_state(request)
    manifest = _latest(state, "marts", "manifest.json")
    return state.docs.docs_payload(manifest, _latest(state, "marts", "catalog.json"), _latest(state, "marts", "run_results.json"))["graph"]


@router.post("/docs/refresh")
def docs_refresh(payload: dict, request: Request) -> dict:
    state = get_state(request)
    run_id = str(payload.get("run_id", "latest"))
    for name in ("manifest.json", "catalog.json", "run_results.json"):
        artifact = state.dbt_rest.get_artifact(run_id, name)  # type: ignore[arg-type]
        state.cache.save_cached(run_id, "marts", artifact)
    manifest = _latest(state, "marts", "manifest.json")
    validate_manifest(manifest)
    state.model_index = state.lineage.build_index(manifest)
    return {"status": "ok", "source": payload.get("source", "manual")}
