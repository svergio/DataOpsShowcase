from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

ALLOWED_TABLES = ("hr_employees", "hr_departments", "hr_positions")


class SchemaLoader:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def load_schema_documents(self) -> list[str]:
        sql = text(
            """
            SELECT table_schema, table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_name = ANY(:allowed)
            ORDER BY table_name, ordinal_position
            """
        )
        grouped: dict[str, list[str]] = {}
        with self.engine.connect() as conn:
            rows = conn.execute(sql, {"allowed": list(ALLOWED_TABLES)}).mappings().all()
        for row in rows:
            table = f"{row['table_schema']}.{row['table_name']}"
            grouped.setdefault(table, []).append(f"{row['column_name']} ({row['data_type']})")
        docs: list[str] = []
        for table, cols in grouped.items():
            docs.append(f"table {table}: columns {', '.join(cols)}")
        if not docs:
            docs = [f"table public.{name}: schema not found yet" for name in ALLOWED_TABLES]
        return docs
