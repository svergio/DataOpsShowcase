from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Request

from app.observability.metrics import WEBHOOK_EVENTS_TOTAL
from app.schemas.contracts import EventPayload
from app.state import AppState

router = APIRouter()


def get_state(request: Request) -> AppState:
    return request.app.state.ctx


def _refresh_for_target(state: AppState, run_id: str, target: str) -> None:
    for name in ("manifest.json", "catalog.json", "run_results.json"):
        try:
            artifact = state.dbt_rest.get_artifact(run_id, name)  # type: ignore[arg-type]
            state.cache.save_cached(run_id, target, artifact)
        except Exception:  # noqa: BLE001
            continue
    manifest = state.storage.get_json(f"dbt-artifacts/latest-success/{target}/manifest.json") or {}
    state.model_index = state.lineage.build_index(manifest)


def _handle_event(
    *,
    event: str,
    target: str,
    payload: EventPayload,
    background_tasks: BackgroundTasks,
    state: AppState,
) -> dict:
    if payload.event_id in state.seen_events:
        WEBHOOK_EVENTS_TOTAL.labels(event=event, status="duplicate").inc()
        return {"status": "ignored", "event": event, "event_id": payload.event_id}
    state.seen_events.add(payload.event_id)
    WEBHOOK_EVENTS_TOTAL.labels(event=event, status="accepted").inc()
    background_tasks.add_task(_refresh_for_target, state, payload.run_id or "latest", target)
    return {"status": "accepted", "event": event, "event_id": payload.event_id}


@router.post("/events/ingestion_completed")
def ingestion_completed(payload: EventPayload, background_tasks: BackgroundTasks, request: Request) -> dict:
    return _handle_event(
        event="ingestion_completed",
        target="staging",
        payload=payload,
        background_tasks=background_tasks,
        state=get_state(request),
    )


@router.post("/events/datavault_completed")
def datavault_completed(payload: EventPayload, background_tasks: BackgroundTasks, request: Request) -> dict:
    return _handle_event(
        event="datavault_completed",
        target="vault",
        payload=payload,
        background_tasks=background_tasks,
        state=get_state(request),
    )


@router.post("/events/marts_completed")
def marts_completed(payload: EventPayload, background_tasks: BackgroundTasks, request: Request) -> dict:
    return _handle_event(
        event="marts_completed",
        target="marts",
        payload=payload,
        background_tasks=background_tasks,
        state=get_state(request),
    )
