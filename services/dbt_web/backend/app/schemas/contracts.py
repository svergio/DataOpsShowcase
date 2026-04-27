from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ArtifactName = Literal["manifest.json", "catalog.json", "run_results.json", "graph.js"]
TargetName = Literal["staging", "vault", "marts"]


class RunJobRequest(BaseModel):
    selectors: list[str] = Field(default_factory=list)
    vars: dict[str, str] = Field(default_factory=dict)
    full_refresh: bool = False
    defer: bool = False
    fail_on_test_failure: bool = True


class RunJobResponse(BaseModel):
    run_id: str
    status: str
    submitted_at: datetime | None = None
    target: TargetName


class RunStatusResponse(BaseModel):
    run_id: str
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_sec: float | None = None
    job_name: str | None = None
    artifacts: list[str] = Field(default_factory=list)


class RunLogsResponse(BaseModel):
    run_id: str
    lines: list[str] = Field(default_factory=list)
    truncated: bool = False
    updated_at: datetime | None = None


class ArtifactEnvelope(BaseModel):
    run_id: str
    name: ArtifactName
    etag: str | None = None
    size: int | None = None
    content_type: str | None = None
    cached: bool = False
    content: dict | str | None = None


class EventPayload(BaseModel):
    event_id: str
    dag_id: str
    run_id: str | None = None
    event_ts: datetime
    target_layer: str | None = None
    upstream_run_ref: str | None = None


class ModelSearchResponse(BaseModel):
    total: int
    items: list[dict]
