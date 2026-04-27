from __future__ import annotations

from typing import Any

from airflow.providers.postgres.hooks.postgres import PostgresHook

from services.common.logging_utils import get_logger

logger = get_logger(__name__)


def _autocommit_connection(conn_id: str) -> Any:
    hook = PostgresHook(postgres_conn_id=conn_id)
    conn = hook.get_conn()
    conn.autocommit = True
    return conn


def ensure_indexes(conn_id: str, indexes: list[dict[str, Any]]) -> int:
    created = 0
    conn = _autocommit_connection(conn_id)
    try:
        with conn.cursor() as cur:
            for idx in indexes:
                cols = ", ".join(idx["columns"])
                where = f" WHERE {idx['where']}" if idx.get("where") else ""
                sql = (
                    f"CREATE INDEX IF NOT EXISTS {idx['name']} "
                    f"ON {idx['table']} ({cols}){where}"
                )
                cur.execute(sql)
                created += 1
                logger.info(
                    "serving index ensured",
                    extra={"extra_payload": {"index": idx["name"], "table": idx["table"]}},
                )
    finally:
        conn.close()
    return created


def vacuum_analyze(conn_id: str, tables: list[str]) -> None:
    conn = _autocommit_connection(conn_id)
    try:
        with conn.cursor() as cur:
            for table in tables:
                cur.execute(f"VACUUM (ANALYZE) {table}")
                logger.info(
                    "serving vacuum analyze",
                    extra={"extra_payload": {"table": table}},
                )
    finally:
        conn.close()


def reindex(conn_id: str, tables: list[str]) -> None:
    conn = _autocommit_connection(conn_id)
    try:
        with conn.cursor() as cur:
            for table in tables:
                cur.execute(f"REINDEX TABLE {table}")
                logger.info(
                    "serving reindex",
                    extra={"extra_payload": {"table": table}},
                )
    finally:
        conn.close()
