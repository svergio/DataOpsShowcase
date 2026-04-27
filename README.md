# DataOpsShowcase

> **Песочница полного контура Data Platform** в одном монорепозитории: от синтетических источников до витрин, MLflow и дашбордов.

**DataOpsShowcase** эмулирует цепочку, похожую на продуктовую: **OLTP, Kafka, MinIO** → ingestion и **Apache Airflow** → **Apache Spark** → **dbt** (включая **Data Vault 2.0**), витрины, **ML** (Spark + **MLflow**), наблюдаемость (**Prometheus / Grafana**). Сверху — **dbt-web** (Flask): запуски, тесты, lineage, ссылки на артефакты dbt.

Это **учебно-демонстрационный** стенд: можно безопасно экспериментировать, показывать архитектуру **инженерам, аналитикам и бизнесу** ([docs/business/](docs/business/)) — без претензии на промышленную безопасность и масштаб.

---

## Зачем этот репозиторий

| Для кого | Что даёт |
|----------|----------|
| Инженеры data/platform | end-to-end практика: оркестрация, dbt, Spark, Kafka, DWH |
| Аналитики и data-инженеры | понятный путь «от сырья до marts» и контроль качества |
| Руководство / продукт | наглядный разговор о стоимости сроков и слоёв — без боевых данных |
| Учёба и онбординг | единая среда, повторяемые сценарии, документация на русском |

---

## Ключевые компоненты

| Область | В репозитории |
|--------|---------------|
| Данные | [generators/](generators/) → Kafka, MinIO, PostgreSQL (OLTP) |
| Хранение и витрины | PostgreSQL (схемы dbt: staging, vault, marts) — см. [docs/diagrams/dwh-schemas.md](docs/diagrams/dwh-schemas.md) |
| Обработка | [spark/](spark/) (jobs, `common/`), [dbt/](dbt/) |
| Оркестрация | [pipelines/](pipelines/) — Airflow DAG, datasets |
| ML | [ml/](ml/) — обучение, фичи, вывод, MLflow |
| Сервисы | [services/](services/) — dbt-web, общий Python |
| Конфигурация | [configs/](configs/), [infra/](infra/) (ingress, мониторинг) |
| Документация | [docs/](docs/) — архитектура, API, дорожная карта, схемы |

---

## Как развернуть (локально)

**Требования:** Docker и Docker Compose (V2, команда `docker compose`).  
Опционально: Python 3.11+ — для [локальных тестов](docs/SETUP.md) и разработки `dbt-web`.

### Шаги

1. Клонировать репозиторий и перейти в корень проекта `DataOpsShowcase/` (там лежит `docker-compose.yml`).

2. Подготовить окружение:

   ```bash
   cp .env.example .env
   ```

   При необходимости отредактировать `.env` (порты: чаще всего `INGRESS_PORT`, `DBT_WEB_BACKEND_PORT` — см. комментарии в шаблоне).

3. Поднять весь стек в фоне:

   ```bash
   docker compose up -d
   ```

4. Подождать, пока контейнеры станут `healthy` (первый старт Airflow/Postgres может занять 1–3 минуты):

   ```bash
   docker compose ps
   ```

5. Открыть **единую точку входа** — nginx **ingress** (по умолчанию порт **8090**).

### С чего начать в браузере

База: `http://localhost:8090` (или ваш `http://localhost:${INGRESS_PORT}` из `.env`).

| URL (относительно ingress) | Что смотреть |
|----------------------------|----------------|
| `/dbt-web/` | Веб-UI: runs, модели, тесты, lineage (логин: см. [docs/WEB_UI_ACCESS.md](docs/WEB_UI_ACCESS.md)) |
| `/airflow/` | Панель Airflow: DAG, ручной запуск, логи |
| `/mlflow/` | MLflow: эксперименты и артефакты |
| `/grafana/` | Grafana: дашборды (логин в `.env`) |
| `/dbt-api/v1/health` | Проверка, что API dbt-web отвечает за ingress |

**Логины и типичные поломки (404/502):** [docs/WEB_UI_ACCESS.md](docs/WEB_UI_ACCESS.md).  
**Порты и переменные без nginx:** тот же файл и [docs/API.md](docs/API.md).

---

## Документация (навигация)

| Документ | Содержание |
|----------|------------|
| [docs/PROJECT_SUMMARY.md](docs/PROJECT_SUMMARY.md) | Сводка: стек, поток данных |
| [docs/SETUP.md](docs/SETUP.md) | Подробный запуск, тесты, CI |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Монорепо и интеграция сервисов |
| [docs/PIPELINES.md](docs/PIPELINES.md) | DAG и цепочка datasets |
| [docs/Roadmap.md](docs/Roadmap.md) | Дорожная карта: ETL/ML, приоритеты |
| [docs/Generators.md](docs/Generators.md) | Синтетика и источники |
| [docs/business/](docs/business/) | Тексты для нетехнических читателей |
| [docs/diagrams/](docs/diagrams/) | Схемы DWH, OLTP, Kafka, MinIO, Data Vault |

---

## Важно

Песочница **намеренно** упрощена в части ИБ, отказоустойчивости и операционных регламентов крупного продакшена. Подходит для **обучения, прототипов и демо**; для боя нужны отдельная оценка рисков, доступов и SLO.
