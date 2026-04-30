# Наблюдаемость и логирование

Как устроены метрики, дашборды и служебные данные о прогонах — **отдельно** от прогонки тестов качества данных dbt (см. [TESTING_AND_DATA_QUALITY.md](TESTING_AND_DATA_QUALITY.md)).

## Канонический путь: `infra/monitoring/`

Рантайм **Prometheus / Grafana** задаётся конфигурацией под [`infra/monitoring/`](../infra/monitoring/), а не топ-уровневым удалённым каталогом `monitoring/quality/`.

| Ресурс | Расположение |
|--------|----------------|
| Prometheus | [`infra/monitoring/prometheus.yml`](../infra/monitoring/prometheus.yml) |
| Provisioning Grafana | [`infra/monitoring/grafana/provisioning/`](../infra/monitoring/grafana/provisioning/) |
| Дашборды (источник правды) | [`infra/monitoring/grafana/dashboards/`](../infra/monitoring/grafana/dashboards/) — в т.ч. `meta-telemetry-postgres.json`, `data-quality-dbt.json`, `pipeline-health-airflow.json` и др. |

В [`docker-compose.yml`](../docker-compose.yml) эти пути монтируются в контейнеры наблюдаемости. В UI: **Meta telemetry (Postgres)** — SQL-панели по `meta.*` и DWH; другие — Pushgateway / Airflow метрики.

Отличие от **dbt DQ**: дашборды показывают *состояние прогонов и метрики*; падающие dbt-тесты и выгрузка в `dwh_dq` — это отдельная зона, см. [TESTING_AND_DATA_QUALITY.md](TESTING_AND_DATA_QUALITY.md).

## Метаданные и витрины в Postgres (OLAP)

- **`meta.pipeline_runs`**: строки создаются через `services.common.run_metadata.start_run` (`status='running'`) и закрываются через `finish_run` с `finished_at`, `status` в `running` | `success` | `failed`, опционально `rows_in`, `rows_out`, `payload`.
- **`meta.pipeline_watermarks`**: чтение/запись через `services.common.watermarks` (конфиг [`configs/pipeline/watermarks.yaml`](../configs/pipeline/watermarks.yaml)).
- Отладка: `meta.v_pipeline_runs_recent`, `meta.v_dq_recent` и другие `meta.v_*` — см. панели Grafana **Meta telemetry (Postgres)** и SQL datasource **PostgreSQL DWH** (`uid: PGDWH`).

Результаты DQ из оркестрации также отражаются в `meta.dq_results`; подробности см. [PIPELINES.md](PIPELINES.md) (раздел наблюдаемости).

## Prometheus и Pushgateway

Airflow публикует метрики вида `dag_success_total`, `dag_failure_total`, `task_duration_seconds_*` через Pushgateway listener. Вспомогательный код dbt в DAG может отправлять метрики `dataops_dbt_*`.

## Логи приложений

В оркестрации и общих сервисах используется структурированный вывод (см. упоминание `JsonFormatter` в `services/common/logging_utils.py` в [PIPELINES.md](PIPELINES.md)). Детальная настройка зависит от сервиса и переменных окружения в compose.

## Контракт ingress (кратко)

Единая точка входа (см. также [QUALITY_AND_MONITORING.md](QUALITY_AND_MONITORING.md)): `/`, `/dbt/`, `/dbt-api/v1/*`, `/airflow/`, `/mlflow/`, `/grafana/`.

## Чек-лист отладки

1. Маршруты: `make smoke` ([`scripts/smoke_ingress.sh`](../scripts/smoke_ingress.sh)).
2. Слой dbt/DQ отдельно: [TESTING_AND_DATA_QUALITY.md](TESTING_AND_DATA_QUALITY.md); при необходимости `./scripts/run_dqc.sh`.
3. Метаданные прогонов: запросы к `meta.v_*` или дашборды в Grafana.
4. Расширенные проверки: `make p0-verify`.

Runbook-фрагмент (исторически из `monitoring/quality/docs/runbook.md`) встроен в разделы выше; дублировать отдельным файлом не требуется.
