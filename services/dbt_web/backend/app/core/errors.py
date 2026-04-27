from __future__ import annotations


class DbtWebError(Exception):
    def __init__(self, error_code: str, message: str, *, upstream_status: int | None = None, details: dict | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.upstream_status = upstream_status
        self.details = details or {}


def error_payload(exc: DbtWebError, trace_id: str) -> tuple[int, dict]:
    status_code = 502 if exc.upstream_status else 400
    payload = {
        "error_code": exc.error_code,
        "message": exc.message,
        "details": exc.details,
        "upstream_status": exc.upstream_status,
        "trace_id": trace_id,
    }
    return status_code, payload
