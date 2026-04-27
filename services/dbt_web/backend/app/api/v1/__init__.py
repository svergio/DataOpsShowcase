from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import artifacts, docs, events, health, lineage, models, runs

router = APIRouter(prefix="/api/v1")
router.include_router(health.router, tags=["health"])
router.include_router(runs.router, tags=["runs"])
router.include_router(artifacts.router, tags=["artifacts"])
router.include_router(models.router, tags=["models"])
router.include_router(lineage.router, tags=["lineage"])
router.include_router(docs.router, tags=["docs"])
router.include_router(events.router, tags=["events"])
