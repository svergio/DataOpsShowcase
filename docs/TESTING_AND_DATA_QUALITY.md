# Тестирование и Data Quality

Где живут проверки в монорепозитории, как они запускаются и как от них отличать **наблюдаемость** (Grafana, метрики) — см. [OBSERVABILITY_AND_LOGGING.md](OBSERVABILITY_AND_LOGGING.md).

## Где искать код тестов

| Тип | Каталог | Запуск |
|-----|---------|--------|
| Pytest (генератор, конфиги, константы, Kafka-билдеры, совместимость layout dbt/Spark) | [`tests/`](../tests/) (`unit`, `integration`) | `pytest tests/unit`; интеграции — см. [SETUP.md](SETUP.md) |
| Архитектурная проверка layout dbt | [`tests/unit/test_dbt_project_layout.py`](../tests/unit/test_dbt_project_layout.py) | `pytest tests/unit/test_dbt_project_layout.py` |
| SQL-тесты dbt (**generic**, DQ-слой) | [`dbt/tests/`](../dbt/tests/) | `cd dbt && dbt test …` |
| Smoke API сервиса **dbt-web** | [`services/dbt_web/backend/tests/`](../services/dbt_web/backend/tests/) | pytest из каталога бэкенда или CI |

Интерпретация «половины тестов в разных местах»: это **разные исполнители** — интерпретатор Python (`pytest`) и CLI **`dbt`**. Последнему нужен свой проект под [`dbt/dbt_project.yml`](../dbt/dbt_project.yml); путь по умолчанию:

```yaml
test-paths: ["tests"]
```

относится к корню **dbt-проекта** (`DataOpsShowcase/dbt/`), поэтому SQL-тесты Data Quality лежат в **`dbt/tests/`**, а не в корне `tests/`. Перенос каталога SQL-тестов в другой топ-уровневый узел монорепо без смены `test-paths` ломает `dbt test`.

## Конфигурация DQ в dbt

- Селектор всех декларативных тестов: **`dqc_all_tests`** — [`dbt/selectors.yml`](../dbt/selectors.yml).
- При падении проверок артефакты складываются в схему **`dwh_dq`** (`store_failures: true` в [`dbt/dbt_project.yml`](../dbt/dbt_project.yml)).

Локально (PostgreSQL OLAP доступен, установлен `dbt`), из корня репозитория:

```bash
./scripts/run_dqc.sh
```

Эквивалент руками:

```bash
cd dbt
dbt source freshness --profiles-dir . --project-dir .
dbt test --selector dqc_all_tests --profiles-dir . --project-dir .
```

## Связка с пайплайном и Makefile

- **Ingress-проверки:** `make smoke` — см. [`scripts/smoke_ingress.sh`](../scripts/smoke_ingress.sh).
- **Расширенные P0:** `make p0-verify` — [`scripts/p0_verify.sh`](../scripts/p0_verify.sh).
- Команда-подсказка: `make dqc-help`.

Airflow выполняет отдельный DAG качества данных (см. [PIPELINES.md](PIPELINES.md)); он не заменяет локальный pytest/dbt-тестами при разработке.

## Аудит дубликатов (исторический контекст)

Ранее существовал каталог топ-уровня `monitoring/quality/` с обёртками и README; он создавал впечатление, что DQ «живёт там», хотя **исполнимые** проверки dbt всегда были только под `dbt/`. Каталог удалён в пользу `scripts/run_dqc.sh` и этого документа. Единственный канон **дашбордов Grafana**: [`infra/monitoring/grafana/`](../infra/monitoring/grafana/) (см. [OBSERVABILITY_AND_LOGGING.md](OBSERVABILITY_AND_LOGGING.md)).
