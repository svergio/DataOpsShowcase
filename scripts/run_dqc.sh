#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}/dbt"
dbt source freshness --profiles-dir . --project-dir .
dbt test --selector dqc_all_tests --profiles-dir . --project-dir .
