# TechMart Data Platform Showcase

Пет-проект дата-платформы для аналитики маркетплейса.

## Цели проекта

- Построить end-to-end batch и streaming пайплайны данных
- Практиковать оркестрацию пайплайнов через Airflow
- Выполнить трансформации данных в dbt и Spark
- Добавить проверки качества данных и мониторинг
- Реализовать аналитические витрины и обработку, близкую к real-time

## Структура репозитория

- `pipelines` - DAG'и Airflow, плагины, датасеты, утилиты
- `services` - общие библиотеки (storage, kafka, dbt client, логи/метрики) и конфиги сервисов (Postgres, Airflow, MinIO, Redis)
- `services/dbt_web` - UI для dbt (backend FastAPI + frontend)
- `spark/jobs` - PySpark entrypoints, `spark/common` - общий код с JDBC/Spark
- `ml` - обучение (Spark/MLflow), конфиги и заготовки features/inference
- `generators` - генераторы данных: `common/` (фабрики, схемы, коннекторы), `kafka/`, `generator.py`, Docker
- `dbt` - dbt: staging, vault, marts, serving, тесты, макросы
- `configs` - YAML пайплайнов, Airflow, spark defaults
- `infra` - init SQL, Prometheus, Grafana
- `scripts` - вспомогательные CLI (публикация артефактов dbt)
- `docs` - [README.md](docs/README.md) (EN), [ARCHITECTURE.md](docs/ARCHITECTURE.md), [PIPELINES.md](docs/PIPELINES.md), [ML.md](docs/ML.md), [SETUP.md](docs/SETUP.md)
- `tests` - pytest (unit)
- `streaming` - дополнительные модули streaming (если используются)

## Задания

Описание задач находится в:

- `Task.md` - исходный документ
- `docs/Tasks` - отдельные файлы задач (`Task_01...Task_50`)

## Быстрый старт

1. Клонировать репозиторий
2. Настроить переменные окружения
3. Поднять локальные сервисы через Docker Compose
4. Начать выполнение задач по порядку из `docs/Tasks`
