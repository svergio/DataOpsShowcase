from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError


def is_retryable_execution_error(exc: BaseException) -> bool:
    if isinstance(exc, DBAPIError):
        orig = exc.orig
        if orig is not None:
            code = getattr(orig, "pgcode", None)
            if code in ("42601", "42P01", "42703"):
                return True
    msg = str(exc).lower()
    if "syntax error" in msg:
        return True
    if "does not exist" in msg and ("relation" in msg or "column" in msg):
        return True
    return False


@dataclass
class DBClient:
    db_url: str

    def __post_init__(self) -> None:
        self.engine: Engine = create_engine(self.db_url, future=True, pool_pre_ping=True)

    def run_select(self, sql: str) -> list[dict[str, object]]:
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql)).mappings().all()
            return [dict(r) for r in rows]

    def ping(self) -> bool:
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
