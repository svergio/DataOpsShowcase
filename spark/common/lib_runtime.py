from __future__ import annotations

import re
from datetime import datetime, timezone

JDBC_DRIVER = "org.postgresql.Driver"


def jdbc_props(user: str, password: str) -> dict[str, str]:
    return {
        "user": user,
        "password": password,
        "driver": JDBC_DRIVER,
        "stringtype": "unspecified",
    }


def parse_execution_ts(execution_ts: str) -> datetime:
    txt = execution_ts.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(txt)
    except ValueError:
        dt = datetime.strptime(execution_ts[:19], "%Y-%m-%dT%H:%M:%S")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def execution_slug(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y%m%d_%H%M%S")


def safe_table_token(target: str) -> str:
    return re.sub(r"[^0-9a-zA-Z_]", "_", target)

