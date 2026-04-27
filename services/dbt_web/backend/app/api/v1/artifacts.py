from __future__ import annotations

from fastapi import APIRouter, Request

from app.schemas.contracts import ArtifactEnvelope, ArtifactName
from app.state import AppState

router = APIRouter()


def get_state(request: Request) -> AppState:
    return request.app.state.ctx


@router.get("/runs/{run_id}/artifacts/{name}", response_model=ArtifactEnvelope)
def get_artifact(run_id: str, name: ArtifactName, request: Request, target: str = "manual") -> ArtifactEnvelope:
    state = get_state(request)
    cached = state.cache.get_cached(run_id, name, target=target)
    if cached is not None:
        return cached
    artifact = state.dbt_rest.get_artifact(run_id, name)
    state.cache.save_cached(run_id, target, artifact)
    return artifact
