from __future__ import annotations

import re
from pathlib import Path

import yaml


def _normalize_sql(text: str) -> str:
    text = re.sub(r"--.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_extension_block_from_04(sql_04: str) -> str:
    start_marker = "-- Extension OLTP landing + Kafka extension"
    end_marker = "CREATE TABLE IF NOT EXISTS staging.stg_customers"
    start = sql_04.find(start_marker)
    end = sql_04.find(end_marker)
    assert start != -1, "04_dwh_extensions.sql: extension block start marker not found"
    assert end != -1, "04_dwh_extensions.sql: extension block end marker not found"
    assert start < end, "04_dwh_extensions.sql: extension block markers are out of order"
    return sql_04[start:end]


def _extract_raw_table_names(sql_text: str) -> set[str]:
    pattern = r"CREATE TABLE IF NOT EXISTS\s+(raw\.[a-z0-9_]+)\s*\("
    return set(re.findall(pattern, sql_text, flags=re.IGNORECASE))


def test_dwh_extension_block_in_04_matches_06_sql() -> None:
    root = Path(__file__).resolve().parents[2]
    sql_04 = (root / "services" / "postgres" / "init" / "04_dwh_extensions.sql").read_text(encoding="utf-8")
    sql_06 = (root / "services" / "postgres" / "init" / "06_dwh_raw_generators_extensions.sql").read_text(
        encoding="utf-8"
    )

    extension_block_04 = _extract_extension_block_from_04(sql_04)
    assert _normalize_sql(extension_block_04) == _normalize_sql(sql_06)


def test_ingestion_oltp_tables_are_created_in_04_sql() -> None:
    root = Path(__file__).resolve().parents[2]
    ingestion = yaml.safe_load((root / "configs" / "pipeline" / "ingestion.yaml").read_text(encoding="utf-8"))
    sql_04 = (root / "services" / "postgres" / "init" / "04_dwh_extensions.sql").read_text(encoding="utf-8")

    yaml_targets = {
        str(item["target_table"])
        for item in ingestion.get("oltp", {}).get("tables", [])
        if str(item.get("target_table", "")).startswith("raw.oltp_")
    }
    sql_tables = _extract_raw_table_names(sql_04)

    missing = sorted(yaml_targets - sql_tables)
    assert not missing, f"Missing raw OLTP tables in 04_dwh_extensions.sql: {missing}"
