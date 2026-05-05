from __future__ import annotations

import logging
from typing import Any

_pipeline_logger = logging.getLogger("nl2sql.pipeline")


def log_nl2sql_stage(trace_id: str, event: str, **fields: Any) -> None:
    payload: dict[str, Any] = {"event": event, "trace_id": trace_id, **fields}
    _pipeline_logger.info(event, extra={"nl2sql": payload})
