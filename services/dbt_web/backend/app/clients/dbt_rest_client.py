from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from app.core.config import settings
from app.core.errors import DbtWebError
from app.schemas.contracts import (
    ArtifactEnvelope,
    ArtifactName,
    RunJobRequest,
    RunJobResponse,
    RunLogsResponse,
    RunStatusResponse,
    TargetName,
)


class DbtRestClient:
    def __init__(self) -> None:
        headers = {"Accept": "application/json"}
        if settings.dbt_rest_token:
            headers["Authorization"] = f"Bearer {settings.dbt_rest_token}"
        self.client = httpx.Client(
            base_url=settings.dbt_rest_base_url.rstrip("/"),
            headers=headers,
            timeout=httpx.Timeout(connect=3.0, read=settings.dbt_rest_timeout_sec, write=10.0, pool=10.0),
        )

    @retry(
        reraise=True,
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=0.5, max=20.0),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError)),
    )
    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        response = self.client.request(method, path, **kwargs)
        if response.status_code in {429, 500, 502, 503, 504}:
            raise httpx.ReadTimeout(f"retryable upstream status: {response.status_code}")
        return response

    def _safe_json(self, response: httpx.Response) -> dict[str, Any]:
        try:
            return response.json()
        except ValueError:
            return {}

    def run_job(self, target: TargetName, payload: RunJobRequest) -> RunJobResponse:
        body = payload.model_dump()
        try:
            response = self._request("POST", f"/jobs/run/{target}", json=body)
        except httpx.HTTPError as exc:
            raise DbtWebError("UPSTREAM_UNAVAILABLE", str(exc)) from exc
        if response.status_code >= 400:
            raise DbtWebError(
                "UPSTREAM_RUN_ERROR",
                "dbt run trigger failed",
                upstream_status=response.status_code,
                details=self._safe_json(response),
            )
        data = self._safe_json(response)
        return RunJobResponse(
            run_id=str(data.get("run_id") or data.get("id")),
            status=str(data.get("status", "queued")),
            submitted_at=datetime.now(timezone.utc),
            target=target,
        )

    def get_run_status(self, run_id: str) -> RunStatusResponse:
        try:
            response = self._request("GET", f"/runs/{run_id}/status")
        except httpx.HTTPError as exc:
            raise DbtWebError("UPSTREAM_UNAVAILABLE", str(exc)) from exc
        if response.status_code >= 400:
            raise DbtWebError(
                "UPSTREAM_STATUS_ERROR",
                "failed to fetch run status",
                upstream_status=response.status_code,
                details=self._safe_json(response),
            )
        data = self._safe_json(response)
        return RunStatusResponse(
            run_id=run_id,
            status=str(data.get("status", "unknown")),
            started_at=data.get("started_at"),
            finished_at=data.get("finished_at"),
            duration_sec=data.get("duration_sec"),
            job_name=data.get("job_name"),
            artifacts=list(data.get("artifacts", [])),
        )

    def get_run_logs(self, run_id: str) -> RunLogsResponse:
        try:
            response = self._request("GET", f"/runs/{run_id}/logs")
        except httpx.HTTPError as exc:
            raise DbtWebError("UPSTREAM_UNAVAILABLE", str(exc)) from exc
        if response.status_code >= 400:
            raise DbtWebError(
                "UPSTREAM_LOGS_ERROR",
                "failed to fetch run logs",
                upstream_status=response.status_code,
                details=self._safe_json(response),
            )
        text = response.text
        return RunLogsResponse(
            run_id=run_id,
            lines=text.splitlines(),
            truncated=False,
            updated_at=datetime.now(timezone.utc),
        )

    def get_artifact(self, run_id: str, name: ArtifactName) -> ArtifactEnvelope:
        try:
            response = self._request(
                "GET",
                f"/artifacts/{run_id}/{name}",
                timeout=httpx.Timeout(connect=3.0, read=60.0, write=10.0, pool=10.0),
            )
        except httpx.HTTPError as exc:
            raise DbtWebError("UPSTREAM_UNAVAILABLE", str(exc)) from exc
        if response.status_code >= 400:
            raise DbtWebError(
                "UPSTREAM_ARTIFACT_ERROR",
                "failed to fetch artifact",
                upstream_status=response.status_code,
                details=self._safe_json(response),
            )
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            content: dict | str | None = self._safe_json(response)
        else:
            content = response.text
        return ArtifactEnvelope(
            run_id=run_id,
            name=name,
            etag=response.headers.get("etag"),
            size=int(response.headers.get("content-length", "0")) or None,
            content_type=content_type or None,
            cached=False,
            content=content,
        )
