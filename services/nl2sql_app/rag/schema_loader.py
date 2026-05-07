from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

from nl2sql.schema_config import CANONICAL_TABLES

ALLOWED_TABLES = tuple(CANONICAL_TABLES)


class SchemaLoader:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def load_schema_documents(self) -> list[str]:
        allowed_pairs: list[tuple[str, str]] = []
        for table in ALLOWED_TABLES:
            schema, name = table.split(".", 1)
            allowed_pairs.append((schema, name))

        sql = text(
            """
            SELECT table_schema, table_name, column_name, data_type
            FROM information_schema.columns
            WHERE (table_schema, table_name) IN (
                SELECT x.table_schema, x.table_name
                FROM unnest(:allowed_schemas, :allowed_names) AS x(table_schema, table_name)
            )
            ORDER BY table_name, ordinal_position
            """
        )
        grouped: dict[str, list[str]] = {}
        with self.engine.connect() as conn:
            rows = conn.execute(
                sql,
                {
                    "allowed_schemas": [schema for schema, _ in allowed_pairs],
                    "allowed_names": [name for _, name in allowed_pairs],
                },
            ).mappings().all()
        for row in rows:
            table = f"{row['table_schema']}.{row['table_name']}"
            grouped.setdefault(table, []).append(f"{row['column_name']} ({row['data_type']})")
        docs: list[str] = []
        for table, cols in grouped.items():
            docs.append(f"table {table}: columns {', '.join(cols)}")
        if not docs:
            docs = [f"table public.{name}: schema not found yet" for name in ALLOWED_TABLES]
        return docs
