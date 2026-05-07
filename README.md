# DataOpsShowcase

Демонстрационный **Data Platform** в одном репозитории: от синтетики и Kafka до витрин, MLflow, Grafana и дашбордов. Подходит для **обучения, демо и прототипов** — не как готовый продакшен.

## Быстрый старт

1. Перейти в каталог `DataOpsShowcase/` (рядом с `docker-compose.yml`).
2. `cp .env.example .env` — при необходимости поправить порты (`INGRESS_PORT`, см. комментарии в `.env`).
3. `docker compose up -d`
4. Подождать `healthy` у основных сервисов: `docker compose ps`.
5. Открыть в браузере **`http://localhost:8090`** (или ваш `INGRESS_PORT` из `.env`).

**Важно:** адрес в строке браузера должен совпадать с **`INGRESS_BASE_URL`** в `.env` (схема, хост и порт). Иначе часть UI (например Superset) может вести себя странно — см. [docs/WEB_UI_ACCESS.md](docs/WEB_UI_ACCESS.md).

Проверка после подъёма (опционально): из корня проекта `./scripts/ingress_smoke.sh`.

## Что внутри (кратко)

Один **ingress** отдаёт портал `/`, Airflow, dbt Docs, Grafana, Superset, MLflow и остальное по префиксам — без отдельных пробросов веб-портов на хост (кроме MinIO S3 API и при необходимости БД).

| Куда зайти | Зачем |
|------------|--------|
| [docs/README.md](docs/README.md) | Оглавление всей документации |
| [docs/PROJECT_SUMMARY.md](docs/PROJECT_SUMMARY.md) | Сводка стека и потока данных |
| [docs/SETUP.md](docs/SETUP.md) | Требования, тесты, типичные проблемы |
| [docs/WEB_UI_ACCESS.md](docs/WEB_UI_ACCESS.md) | Таблица URL, логины, типовые 404/502 |

Код и конфиги: `pipelines/` (Airflow), `dbt/`, `spark/`, `services/` (портал, dbt-rest, nl2sql и др.), `configs/`, `infra/` (nginx, мониторинг).

## Architecture + Tools (rollout)

Базовый стенд остается в `docker-compose.yml`, а новые инструменты подключаются как **additive overlays** из `infrastructure/` с profile-gating.

| Профиль | Файл | Назначение | Ключевая команда |
|---------|------|------------|------------------|
| `core` | `docker-compose.yml` | Базовая платформа (ингресс, DWH, Airflow, dbt, Grafana, Superset и т.д.) | `make up-lite` |
| `vault` | `infrastructure/vault/docker-compose.vault.yml` | Secrets management (dev bootstrap, policy scaffolding) | `make vault-init` |
| `lakefs` | `infrastructure/lakefs/docker-compose.lakefs.yml` | Branching/rollback для data lake слоев | `make lakefs-setup` |
| `datahub` | `infrastructure/datahub/docker-compose.datahub.yml` | Metadata catalog dual-run миграция | `make datahub-ingest` |
| `argocd` | `infrastructure/argocd/docker-compose.argocd.yml` | GitOps control plane и promotion flow | `make gitops-sync` |

Полный подъем (core + tooling profiles): `make up`.

## Документация

Полный указатель — **[docs/README.md](docs/README.md)**. Отдельно полезны [PIPELINES.md](docs/PIPELINES.md), [SUPERSET.md](docs/SUPERSET.md), [docs/ML.md](docs/ML.md) (в т.ч. **NL2SQL** за `/nl2sql/`), [services/nl2sql_app/README.md](services/nl2sql_app/README.md), [API.md](docs/API.md), материалы для нетехнических читателей — [docs/business/](docs/business/), диаграммы — [docs/diagrams/](docs/diagrams/).

## Ограничения

Стенд **намеренно** упрощён по ИБ, отказоустойчивости и операционным регламентам «большого» продакшена. Для боя нужны отдельная модель угроз, доступы и SLO.
