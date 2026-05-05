from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterable, Iterator, Sequence

from airflow.providers.postgres.hooks.postgres import PostgresHook
from psycopg2.extras import Json, execute_values


@contextmanager
def pg_cursor(conn_id: str) -> Iterator[Any]:
    hook = PostgresHook(postgres_conn_id=conn_id)
    conn = hook.get_conn()
    try:
        with conn.cursor() as cursor:
            yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def fetch_all(conn_id: str, sql: str, params: Sequence[Any] | None = None) -> list[tuple[Any, ...]]:
    with pg_cursor(conn_id) as cur:
        cur.execute(sql, params or ())
        return cur.fetchall()


def fetch_one(conn_id: str, sql: str, params: Sequence[Any] | None = None) -> tuple[Any, ...] | None:
    with pg_cursor(conn_id) as cur:
        cur.execute(sql, params or ())
        return cur.fetchone()


def execute(conn_id: str, sql: str, params: Sequence[Any] | None = None) -> int:
    with pg_cursor(conn_id) as cur:
        cur.execute(sql, params or ())
        return cur.rowcount or 0


def execute_sequence(
    conn_id: str,
    operations: Sequence[tuple[str, Sequence[Any] | None]],
) -> list[int]:
    hook = PostgresHook(postgres_conn_id=conn_id)
    conn = hook.get_conn()
    rowcounts: list[int] = []
    try:
        with conn.cursor() as cur:
            for sql, params in operations:
                cur.execute(sql, params or ())
                rowcounts.append(cur.rowcount or 0)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return rowcounts


def _adapt_cell(value: Any) -> Any:
    if isinstance(value, dict | list):
        return Json(value)
    return value


def _adapt_row(row: Sequence[Any]) -> tuple[Any, ...]:
    return tuple(_adapt_cell(v) for v in row)


def bulk_insert(
    conn_id: str,
    table: str,
    columns: Sequence[str],
    rows: Iterable[Sequence[Any]],
    *,
    page_size: int = 1000,
    on_conflict: str | None = None,
) -> int:
    rows = [_adapt_row(r) for r in rows]
    if not rows:
        return 0
    columns_sql = ", ".join(columns)
    sql = f"INSERT INTO {table} ({columns_sql}) VALUES %s"
    if on_conflict:
        sql += f" {on_conflict}"
    with pg_cursor(conn_id) as cur:
        execute_values(cur, sql, rows, page_size=page_size)
        return cur.rowcount or 0


def upsert(
    conn_id: str,
    table: str,
    columns: Sequence[str],
    rows: Iterable[Sequence[Any]],
    *,
    conflict_columns: Sequence[str],
    update_columns: Sequence[str] | None = None,
    page_size: int = 1000,
) -> int:
    rows = list(rows)
    if not rows:
        return 0
    update_cols = update_columns or [c for c in columns if c not in conflict_columns]
    if not update_cols:
        on_conflict = (
            f"ON CONFLICT ({', '.join(conflict_columns)}) DO NOTHING"
        )
    else:
        set_sql = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)
        on_conflict = (
            f"ON CONFLICT ({', '.join(conflict_columns)}) DO UPDATE SET {set_sql}"
        )
    return bulk_insert(conn_id, table, columns, rows, page_size=page_size, on_conflict=on_conflict)
