from __future__ import annotations

import re

import sqlglot
from sqlglot import exp

from nl2sql.schema_config import CANONICAL_TABLES, TABLE_ALIASES

ALLOWED_TABLES = frozenset(CANONICAL_TABLES)
BLOCKED_KEYWORDS = ("insert", "update", "delete", "drop", "alter", "truncate")


def _extract_table_name(node: exp.Table) -> str:
    table = str(node.this).lower().replace('"', "") if node.this is not None else ""
    schema = str(node.db).lower().replace('"', "") if node.db is not None else ""
    return f"{schema}.{table}" if schema and table else table


def normalize_llm_sql(raw_sql: str) -> str:
    text = (raw_sql or "").strip()
    if not text:
        return ""

    fence = re.search(r"```(?:sql)?\s*(.*?)```", text, re.IGNORECASE | re.DOTALL)
    if fence:
        text = fence.group(1).strip()

    text = re.sub(r"^\s*`+", "", text)
    text = re.sub(r"`+\s*$", "", text)
    text = re.sub(r"^\s*sql\b[:\s-]*", "", text, flags=re.IGNORECASE)

    select_match = re.search(r"\bselect\b", text, flags=re.IGNORECASE)
    if select_match:
        text = text[select_match.start() :].strip()

    end_match = re.search(r";", text)
    if end_match:
        text = text[: end_match.start() + 1]

    text = re.sub(r"\s+", " ", text).strip()
    return text


def _qualify_allowed_tables(sql_text: str) -> str:
    normalized = sql_text

    for alias, target in TABLE_ALIASES.items():
        normalized = re.sub(
            rf"(?<!\.)\b{re.escape(alias)}\b",
            target,
            normalized,
            flags=re.IGNORECASE,
        )

    for table in ALLOWED_TABLES:
        short = table.split(".")[-1]
        normalized = re.sub(
            rf"(?<!\.)\b{re.escape(short)}\b",
            table,
            normalized,
            flags=re.IGNORECASE,
        )

    return normalized


def validate_sql(sql: str) -> str:
    sql_clean = normalize_llm_sql(sql).rstrip(";")
    if not sql_clean:
        raise ValueError("empty SQL generated")
    sql_clean = _qualify_allowed_tables(sql_clean)
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
