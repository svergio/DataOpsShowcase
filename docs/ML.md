# ML в DataOpsShowcase

Раздел описывает **каталог `ml/`**, связь с **Airflow** и **MLflow**, а не математику конкретных моделей.

## Назначение каталогов

| Путь | Содержание |
|------|------------|
| `ml/training/` | Скрипты обучения (пример: `train_order_value_model.py`) |
| `ml/configs/training_default.yaml` | Параметры/метаданные эксперимента по умолчанию |
| `ml/features/` | Код подготовки признаков |
| `ml/inference/` | Обертки batch/online-инференса |
| `ml/models/` | Метаданные и пути к артефактам (по соглашениям проекта) |

## Оркестрация

- DAG `dag_ml_train_spark` (см. [PIPELINES.md](PIPELINES.md)) поднимает обучение в **Spark**; приложение в контейнере — путь вроде `/opt/airflow/ml/training/... .py` (актуальное имя в DAG).
- Общий Spark-рантайм поставляется из `spark/common/` через `py_files`.

## Данные

- Для стенда обучение может читать из `dwh_staging` (например, `stg_orders`); в прод-подобных сценариях источник переносят на **marts/curated** после согласования.

## MLflow

- **Tracking URI** и имя эксперимента задаются переменными окружения (см. `docker-compose`, переменные в DAG `dag_ml_train_spark`).
- UI MLflow: через ingress, см. [WEB_UI_ACCESS.md](WEB_UI_ACCESS.md).

## NL2SQL-сервис (не каталог `ml/`)

Отдельное приложение **`nl2sql_app`**: RAG по схеме DWH, загрузка модели из **MLflow** (`pyfunc`), ответы по **`POST /query`**. За ingress: **`/nl2sql/`**. Полное описание переменных, health, MLflow и ограничений по памяти — **[services/nl2sql_app/README.md](../services/nl2sql_app/README.md)**; маршрут и типичные сбои — [WEB_UI_ACCESS.md](WEB_UI_ACCESS.md) (раздел NL2SQL). В сводке стека — [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md).

## Минимальный ручной чек-лист

1. Поднять стек и Airflow, убедиться, что `dag_ml_train_spark` виден.
2. Проверить, что в MLflow появляется эксперимент с метриками после прогона.
3. Сверить путь к данным в скрипте с актуальными схемами dbt (см. [diagrams/data_vault_flow.md](diagrams/data_vault_flow.md)).

## См. также

- [ARCHITECTURE.md](ARCHITECTURE.md) — как `ml/` встраивается в монорепо
- [Roadmap.md](Roadmap.md) — приоритеты по ML-задачам (P1/P2)
