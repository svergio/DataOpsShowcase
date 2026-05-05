from __future__ import annotations

import json
import logging
from typing import Any


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        extra = getattr(record, "nl2sql", None)
        if isinstance(extra, dict):
            payload.update(extra)
        if record.exc_info:
            payload["exc_text"] = self.formatException(record.exc_info).strip()
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_json_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    if root.handlers:
        for h in root.handlers:
            if isinstance(h.formatter, JsonFormatter):
                return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
