from __future__ import annotations

import re

import sqlglot
from sqlglot import exp

ALLOWED_TABLES = frozenset({"hr_employees", "hr_departments", "hr_positions"})
BLOCKED_KEYWORDS = ("insert", "update", "delete", "drop", "alter", "truncate")


def _extract_table_name(node: exp.Table) -> str:
    if node.this is None:
        return ""
    return str(node.this).lower()


def validate_sql(sql: str) -> str:
    sql_clean = sql.strip().rstrip(";")
    if not sql_clean:
        raise ValueError("empty SQL generated")
    lowered = sql_clean.lower()
    if any(word in lowered for word in BLOCKED_KEYWORDS):
        raise ValueError("forbidden SQL statement detected")

    parsed = sqlglot.parse_one(sql_clean, read="postgres")
    if not isinstance(parsed, exp.Select):
        raise ValueError("only plain SELECT is allowed")

    used_tables = {_extract_table_name(t) for t in parsed.find_all(exp.Table)}
    unknown = [t for t in used_tables if t and t not in ALLOWED_TABLES]
    if unknown:
        raise ValueError(f"table is not whitelisted: {', '.join(sorted(unknown))}")

    if not parsed.args.get("limit"):
        sql_clean = re.sub(r"\s+$", "", sql_clean) + " LIMIT 100"
    return sql_clean
