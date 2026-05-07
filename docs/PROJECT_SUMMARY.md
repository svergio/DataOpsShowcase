# DataOpsShowcase: сводка проекта

Документ даёт **единый взгляд** на песочницу Data Platform: зачем она существует, из чего собрана и как в ней течёт данные. Подробности для нетехнических читателей — в [docs/business/](business/README.md).

## Что это за песочница

**DataOpsShowcase** — учебно-демонстрационный репозиторий, который эмулирует **замкнутый контур** современной data-платформы: от синтетических источников и потоковой шины до хранения, оркестрации, Data Vault, витрин, ML и observability. Цель — отрабатывать практику «как в продукте», но локально и без риска для боевых данных.

## Бизнес-образ: TechMart

Проект опирается на **условного маркетплейса электроники (TechMart)**: заказы, платежи, поставщики, события веб- и мобильного трафика, файлы в объектном хранилище. Это **не** продакшн-магазин, а **сюжет**, на котором понятны отчёты, витрины и сценарии рисков/логистики. Бизнес-формулировки сценариев — в [use_cases.md](business/use_cases.md).

## Состав стека (по слоям)

| Категория | Технологии в репозитории | Роль |
|-----------|-------------------------|------|
| Потоковые и файловые данные | **Apache Kafka** | События заказов, платежей, кликстрим, доставки |
| Объектное хранилище | **MinIO** (S3-совместимый API) | «Сырые» файлы, выгрузки, артефакты |
| Транзакции | **PostgreSQL (OLTP)** | Справочники и транзакции в стиле маркетплейса |
| Аналитическое хранилище | **PostgreSQL (DWH/схемы dbt)** | Staging, vault, marts, serving |
| Обработка | **Apache Spark** | Препроцессинг, тяжёлые job’ы, ML-обучение в DAG |
| Трансформации | **dbt** | Staging, **Data Vault 2.0** (hubs, links, satellites, BDV), витрины, serving |
| Оркестрация | **Apache Airflow** | DAG, datasets, вызовы dbt/Spark |
| MLOps | **MLflow** | Эксперименты и артефакты обучения |
| Наблюдаемость | **Prometheus**, **Grafana** | Метрики и дашборды |
| Web UI | **dbt Docs** (статика) | Документация и lineage после `dbt docs generate`, префикс `/dbt/` |
| BI и демо UI | **Apache Superset**, NL2SQL (`/nl2sql/`) | Витрины OLAP и текст→SQL; см. [SUPERSET.md](SUPERSET.md), [services/nl2sql_app/README.md](../services/nl2sql_app/README.md) |

Публикация HTTP наружу идёт через **единый nginx ingress**: большинство ссылок в портале — полноценные веб-интерфейсы; префиксы **`/schema-registry/`** и **`/kafka-connect/`** — это **REST/API** (ответы JSON), и они живы только при CDC-overlay ([ARCHITECTURE_CDC.md](ARCHITECTURE_CDC.md)).

Схемы: **контейнеры Docker (C4)** — [diagrams/c4-container.md](diagrams/c4-container.md); **схемы PostgreSQL (DWH)** — [diagrams/dwh-schemas.md](diagrams/dwh-schemas.md); **поток Data Vault** — [diagrams/data_vault_flow.md](diagrams/data_vault_flow.md).

## Как данные проходят через систему (упрощённо)

```text
[OLTP] ──┬──> ingestion (Airflow) ──> raw / staging (БД) ─┐
[Kafka] ─┤                                               ├──> Spark preprocess ──> staging
[MinIO] ─┘                                               │
                                                          v
         Data Vault load (hubs, links, sats) ──> SCD2 ──> dbt (vault / marts / serving)
                                                          │
                                                          ├──> data quality
                                                          ├──> serving (индексы, оптимизация)
                                                          └──> ML training (Spark) ──> MLflow
```

Реальная цепочка DAG, datasets и имён: [PIPELINES.md](PIPELINES.md). Источники и генерация: [Generators.md](Generators.md), [diagrams/README.md](diagrams/README.md).

## Какие задачи удобно тестировать

- **Ingestion**: сравнение сырого слоя с генератором (Kafka, MinIO, OLTP).
- **Пайплайн end-to-end**: прогон цепочки Airflow, проверка `meta.pipeline_*` и витрин.
- **dbt**: `staging` → `vault` → `marts`, тесты и `dbt docs generate`, статический сайт **dbt Docs** по префиксу `/dbt/` (см. [WEB_UI_ACCESS.md](WEB_UI_ACCESS.md)).
- **Business KPI marts**: `mart_daily_business_kpis`, `mart_cohort_retention`, `mart_user_rfm`, `mart_category_performance`, `mart_marketing_channel`, `mart_unit_economics`; запуск DAG `dag_dbt_business_kpis_rest`.
- **Data Vault**: согласованность ссылок hub/link/sat, SCD2.
- **ML**: обучение из DAG, чтение MLflow, сверка с `ml/training/`.
- **Наблюдаемость**: логи, метрики, Grafana.
- **Регресс API**: [API.md](API.md) — health и вызовы **dbt-rest**; CDC-префиксы ingress — REST, см. [WEB_UI_ACCESS.md](WEB_UI_ACCESS.md).

## Связанные документы

| Документ | Назначение |
|----------|------------|
| [README.md](../README.md) | Вход в репозиторий, быстрый старт |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Монорепо, интеграция сервисов |
| [SETUP.md](SETUP.md) | Запуск и окружение |
| [Roadmap.md](Roadmap.md) | Направления доработки (ETL/ML, канал инвестору), приоритеты P0–P2 |
| [business/README.md](business/README.md) | Материалы для бизнеса |
| [business/platform_value.md](business/platform_value.md) | Бизнес-смысл Atlas, портала и мессенджера |

---

*Проект предназначен для обучения и демонстрации. Конфигурация упрощена по сравнению с крупным продом, но направления и приёмы — продуктовые.*
