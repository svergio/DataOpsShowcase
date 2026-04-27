from __future__ import annotations

from fastapi import APIRouter, Query, Request

from app.schemas.contracts import ModelSearchResponse
from app.state import AppState

router = APIRouter()


def get_state(request: Request) -> AppState:
    return request.app.state.ctx


@router.get("/models", response_model=ModelSearchResponse)
def search_models(
    request: Request,
    query: str = "",
    tags: str = "",
    resource_type: str = "",
    schema: str = "",
    package_name: str = "",
) -> ModelSearchResponse:
    items = list(get_state(request).model_index.values())
    if query:
        items = [x for x in items if query.lower() in str(x.get("name", "")).lower()]
    if tags:
        tag_set = set(t.strip() for t in tags.split(",") if t.strip())
        items = [x for x in items if tag_set.intersection(set(x.get("tags", [])))]
    if resource_type:
        items = [x for x in items if x.get("resource_type") == resource_type]
    if schema:
        items = [x for x in items if x.get("schema") == schema]
    if package_name:
        items = [x for x in items if x.get("package_name") == package_name]
    return ModelSearchResponse(total=len(items), items=items)


@router.get("/models/{unique_id}/dependencies")
def dependencies(unique_id: str, request: Request) -> dict:
    state = get_state(request)
    return state.lineage.get_dependencies(state.model_index, unique_id)


@router.get("/exposures")
def exposures(request: Request) -> dict:
    state = get_state(request)
    items = [x for x in state.model_index.values() if x.get("resource_type") == "exposure"]
    return {"total": len(items), "items": items}


@router.get("/freshness")
def freshness(request: Request) -> dict:
    state = get_state(request)
    latest = state.storage.get_json("dbt-artifacts/latest-success/marts/run_results.json") or {}
    return state.freshness.summarize(latest)
