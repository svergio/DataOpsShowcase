from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

import requests

from services.common.logging_utils import get_logger

logger = get_logger(__name__)

TERMINAL_STATES = {"success", "failed", "error", "cancelled", "timeout"}
SUCCESS_STATES = {"success"}


class DbtRestError(RuntimeError):
    pass


class DbtRunFailed(DbtRestError):
    def __init__(self, run_id: str, status: str, payload: dict[str, Any]) -> None:
        super().__init__(f"dbt run {run_id} finished with status={status}")
        self.run_id = run_id
        self.status = status
        self.payload = payload


@dataclass(frozen=True)
class DbtRunRequest:
    job_name: str
    selectors: list[str]
    target: str
    fail_on_test_failure: bool = True
    command: str | None = None
    extra: dict[str, Any] | None = None


@dataclass
class DbtRunResult:
    run_id: str
    status: str
    started_at: str | None
    finished_at: str | None
    artifacts_url: str | None
    raw: dict[str, Any]
    partial: bool = False


def _partial_from_payload(data: dict[str, Any]) -> bool:
    if bool(data.get("partial_success")):
        return True
    detail = str(data.get("status_detail") or "").lower()
    if "partial" in detail:
        return True
    rr = data.get("run_results") or data.get("results")
    if isinstance(rr, dict):
        failed = rr.get("failed") or rr.get("failures")
        if isinstance(failed, int) and failed > 0:
            return True
        if isinstance(failed, list) and len(failed) > 0:
            return True
    return False


class DbtRestClient:
    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        *,
        timeout: int = 30,
        verify_tls: bool = True,
        trigger_max_attempts: int = 5,
        trigger_backoff_seconds: float = 10.0,
        trigger_backoff_factor: float = 2.0,
        poll_interval_seconds: float = 20.0,
        poll_max_total_seconds: float = 7200.0,
        partial_success: str = "ignore",
    ) -> None:
        self.base_url = (base_url or os.environ.get("DBT_REST_BASE_URL", "")).rstrip("/")
        if not self.base_url:
            raise DbtRestError("DBT_REST_BASE_URL is not configured")
        self.token = token or os.environ.get("DBT_REST_TOKEN")
        self.timeout = timeout
        self.verify_tls = verify_tls
        self.trigger_max_attempts = trigger_max_attempts
        self.trigger_backoff_seconds = trigger_backoff_seconds
        self.trigger_backoff_factor = trigger_backoff_factor
        self.poll_interval_seconds = poll_interval_seconds
        self.poll_max_total_seconds = poll_max_total_seconds
        self.partial_success = str(partial_success or "ignore").strip().lower()

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def trigger_run(self, request: DbtRunRequest) -> str:
        url = f"{self.base_url}/runs"
        body = {
            "job": request.job_name,
            "selectors": request.selectors,
            "target": request.target,
            "fail_on_test_failure": request.fail_on_test_failure,
            "command": request.command,
            "extra": request.extra or {},
        }
        attempt = 0
        delay = self.trigger_backoff_seconds
        last_error: Exception | None = None
        while attempt < self.trigger_max_attempts:
            attempt += 1
            try:
                response = requests.post(
                    url,
                    json=body,
                    headers=self._headers(),
                    timeout=self.timeout,
                    verify=self.verify_tls,
                )
                response.raise_for_status()
                data = response.json()
                run_id = str(data.get("run_id") or data.get("id") or "")
                if not run_id:
                    raise DbtRestError(f"trigger response missing run id: {data}")
                logger.info(
                    "dbt run triggered",
                    extra={
                        "extra_payload": {
                            "job": request.job_name,
                            "selectors": request.selectors,
                            "run_id": run_id,
                            "attempt": attempt,
                        }
                    },
                )
                return run_id
            except (requests.RequestException, DbtRestError, ValueError) as exc:
                last_error = exc
                logger.warning(
                    "dbt trigger attempt failed",
                    extra={
                        "extra_payload": {
                            "job": request.job_name,
                            "attempt": attempt,
                            "error": str(exc),
                            "next_delay": delay,
                        }
                    },
                )
                time.sleep(delay)
                delay *= self.trigger_backoff_factor
        raise DbtRestError(f"dbt trigger failed after {self.trigger_max_attempts} attempts: {last_error}")

    def get_run(self, run_id: str) -> dict[str, Any]:
        url = f"{self.base_url}/runs/{run_id}"
        response = requests.get(
            url,
            headers=self._headers(),
            timeout=self.timeout,
            verify=self.verify_tls,
        )
        response.raise_for_status()
        return response.json()

    def fetch_logs(self, run_id: str) -> str | None:
        url = f"{self.base_url}/runs/{run_id}/logs"
        try:
            response = requests.get(
                url,
                headers=self._headers(),
                timeout=self.timeout,
                verify=self.verify_tls,
            )
        except requests.RequestException as exc:
            logger.warning(
                "dbt logs fetch failed",
                extra={"extra_payload": {"run_id": run_id, "error": str(exc)}},
            )
            return None
        if response.status_code != 200:
            return None
        return response.text

    def wait_for_completion(self, run_id: str) -> DbtRunResult:
        deadline = time.monotonic() + self.poll_max_total_seconds
        while True:
            data = self.get_run(run_id)
            status = str(data.get("status") or "").lower()
            logger.info(
                "dbt run status",
                extra={"extra_payload": {"run_id": run_id, "status": status}},
            )
            if status in TERMINAL_STATES:
                partial = status in SUCCESS_STATES and _partial_from_payload(data)
                result = DbtRunResult(
                    run_id=run_id,
                    status=status,
                    started_at=data.get("started_at"),
                    finished_at=data.get("finished_at"),
                    artifacts_url=data.get("artifacts_url"),
                    raw=data,
                    partial=partial,
                )
                if status not in SUCCESS_STATES:
                    raise DbtRunFailed(run_id, status, data)
                if partial:
                    if self.partial_success == "fail":
                        raise DbtRestError(
                            f"dbt run {run_id} reported partial success but partial_success policy is fail"
                        )
                    if self.partial_success == "warn":
                        logger.warning(
                            "dbt run succeeded with partial failures (per API payload)",
                            extra={"extra_payload": {"run_id": run_id}},
                        )
                return result
            if time.monotonic() > deadline:
                raise DbtRestError(
                    f"dbt run {run_id} did not finish within {self.poll_max_total_seconds}s"
                )
            time.sleep(self.poll_interval_seconds)

    def run_and_wait(self, request: DbtRunRequest) -> DbtRunResult:
        run_id = self.trigger_run(request)
        try:
            return self.wait_for_completion(run_id)
        except DbtRunFailed as exc:
            logs = self.fetch_logs(run_id)
            if logs:
                logger.error(
                    "dbt run failed (tail of logs)",
                    extra={
                        "extra_payload": {
                            "run_id": run_id,
                            "status": exc.status,
                            "log_tail": logs[-4000:],
                        }
                    },
                )
            raise


def build_client_from_config(
    rest_cfg: dict[str, Any],
    retry_cfg: dict[str, Any],
    root_cfg: dict[str, Any] | None = None,
) -> DbtRestClient:
    connection = rest_cfg or {}
    root = root_cfg or {}
    base_url = os.environ.get(connection.get("base_url_env", "DBT_REST_BASE_URL"))
    if not base_url:
        base_url = connection.get("default_base_url", "")
    token = os.environ.get(connection.get("token_env", "DBT_REST_TOKEN"))
    return DbtRestClient(
        base_url=base_url,
        token=token,
        timeout=int(connection.get("timeout_seconds", 30)),
        verify_tls=bool(connection.get("verify_tls", False)),
        trigger_max_attempts=int(retry_cfg.get("trigger_max_attempts", 5)),
        trigger_backoff_seconds=float(retry_cfg.get("trigger_backoff_seconds", 10.0)),
        trigger_backoff_factor=float(retry_cfg.get("trigger_backoff_factor", 2.0)),
        poll_interval_seconds=float(retry_cfg.get("poll_interval_seconds", 20.0)),
        poll_max_total_seconds=float(retry_cfg.get("poll_max_total_seconds", 7200.0)),
        partial_success=str(root.get("partial_success", "ignore")),
    )
