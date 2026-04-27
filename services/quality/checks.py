from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from services.common.logging_utils import get_logger
from services.storage.postgres_io import execute, fetch_one

logger = get_logger(__name__)
DWH_CONN_ID = "postgres_dwh"


@dataclass
class CheckResult:
    name: str
    table: str
    severity: str
    passed: bool
    observed: str | None
    expected: str | None
    details: dict[str, Any]


def _record_result(dag_id: str, result: CheckResult) -> None:
    sql = """
        INSERT INTO meta.dq_results (
            dag_id, check_name, table_name, severity, passed,
            observed_value, expected_value, details
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
    """
    execute(
        DWH_CONN_ID,
        sql,
        (
            dag_id,
            result.name,
            result.table,
            result.severity,
            result.passed,
            result.observed,
            result.expected,
            json.dumps(result.details),
        ),
    )


def run_unique(check: dict[str, Any]) -> CheckResult:
    columns = check["columns"]
    cols = ", ".join(columns)
    sql = f"""
        SELECT COUNT(*) FROM (
            SELECT {cols}, COUNT(*) AS c
            FROM {check['table']}
            GROUP BY {cols}
            HAVING COUNT(*) > 1
        ) duplicates
    """
    row = fetch_one(DWH_CONN_ID, sql)
    duplicates = int(row[0]) if row else 0
    return CheckResult(
        name=check["name"],
        table=check["table"],
        severity=check["severity"],
        passed=duplicates == 0,
        observed=str(duplicates),
        expected="0",
        details={"columns": columns},
    )


def run_not_null(check: dict[str, Any]) -> CheckResult:
    columns = check["columns"]
    where = " OR ".join(f"{c} IS NULL" for c in columns)
    sql = f"SELECT COUNT(*) FROM {check['table']} WHERE {where}"
    row = fetch_one(DWH_CONN_ID, sql)
    nulls = int(row[0]) if row else 0
    return CheckResult(
        name=check["name"],
        table=check["table"],
        severity=check["severity"],
        passed=nulls == 0,
        observed=str(nulls),
        expected="0",
        details={"columns": columns},
    )


def run_range(check: dict[str, Any]) -> CheckResult:
    column = check["column"]
    min_value = check.get("min_value")
    max_value = check.get("max_value")
    conditions: list[str] = []
    params: list[Any] = []
    if min_value is not None:
        conditions.append(f"{column} < %s")
        params.append(min_value)
    if max_value is not None:
        conditions.append(f"{column} > %s")
        params.append(max_value)
    if not conditions:
        return CheckResult(
            name=check["name"],
            table=check["table"],
            severity=check["severity"],
            passed=True,
            observed="0",
            expected="0",
            details={"column": column, "note": "no range bounds configured"},
        )
    where = " OR ".join(conditions)
    sql = f"SELECT COUNT(*) FROM {check['table']} WHERE {where}"
    row = fetch_one(DWH_CONN_ID, sql, params)
    violations = int(row[0]) if row else 0
    return CheckResult(
        name=check["name"],
        table=check["table"],
        severity=check["severity"],
        passed=violations == 0,
        observed=str(violations),
        expected="0",
        details={"column": column, "min": min_value, "max": max_value},
    )


def run_referential(check: dict[str, Any]) -> CheckResult:
    sql = f"""
        SELECT COUNT(*) FROM {check['table']} c
        LEFT JOIN {check['parent_table']} p
          ON c.{check['child_column']} = p.{check['parent_column']}
        WHERE p.{check['parent_column']} IS NULL
    """
    row = fetch_one(DWH_CONN_ID, sql)
    orphans = int(row[0]) if row else 0
    return CheckResult(
        name=check["name"],
        table=check["table"],
        severity=check["severity"],
        passed=orphans == 0,
        observed=str(orphans),
        expected="0",
        details={
            "parent_table": check["parent_table"],
            "parent_column": check["parent_column"],
            "child_column": check["child_column"],
        },
    )


def run_scd2_one_current(check: dict[str, Any]) -> CheckResult:
    business_hk = check["business_hk"]
    sql = f"""
        SELECT COUNT(*) FROM (
            SELECT {business_hk}, COUNT(*) AS c
            FROM {check['table']}
            WHERE is_current = TRUE
            GROUP BY {business_hk}
            HAVING COUNT(*) > 1
        ) violations
    """
    row = fetch_one(DWH_CONN_ID, sql)
    violations = int(row[0]) if row else 0
    return CheckResult(
        name=check["name"],
        table=check["table"],
        severity=check["severity"],
        passed=violations == 0,
        observed=str(violations),
        expected="0",
        details={"business_hk": business_hk},
    )


_DISPATCH = {
    "unique": run_unique,
    "not_null": run_not_null,
    "range": run_range,
    "referential": run_referential,
    "scd2_one_current": run_scd2_one_current,
}


def execute_checks(
    *,
    dag_id: str,
    checks: list[dict[str, Any]],
    fail_on: list[str],
) -> tuple[list[CheckResult], list[CheckResult]]:
    results: list[CheckResult] = []
    failures: list[CheckResult] = []
    for check in checks:
        runner = _DISPATCH.get(check["type"])
        if runner is None:
            raise ValueError(f"unknown DQ check type: {check['type']}")
        try:
            result = runner(check)
        except Exception as exc:
            logger.exception(
                "dq check raised",
                extra={"extra_payload": {"check": check.get("name"), "error": str(exc)}},
            )
            result = CheckResult(
                name=check["name"],
                table=check["table"],
                severity=check["severity"],
                passed=False,
                observed=None,
                expected=None,
                details={"error": str(exc)},
            )
        _record_result(dag_id, result)
        results.append(result)
        if not result.passed and result.severity in fail_on:
            failures.append(result)
        logger.info(
            "dq check executed",
            extra={
                "extra_payload": {
                    "check": result.name,
                    "table": result.table,
                    "severity": result.severity,
                    "passed": result.passed,
                    "observed": result.observed,
                }
            },
        )
    return results, failures
