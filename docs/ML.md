# ML-пайплайны

## Структура

| Путь | Назначение |
| --- | --- |
| `ml/training/` | Скрипты обучения (например, `train_order_value_model.py`) |
| `ml/configs/training_default.yaml` | Дефолтные гиперпараметры/метаданные эксперимента |
| `ml/features/` | Код подготовки признаков |
| `ml/inference/` | Batch/online inference обвязка |
| `ml/models/` | Метаданные/артефакты моделей |

## Airflow

- DAG `dag_ml_train_spark` запускает обучение в Spark.
- Путь приложения в контейнере: `/opt/airflow/ml/training/train_order_value_model.py`.
- Общие Spark-утилиты поставляются из `spark/common/` через `py_files`.

## Источники данных

Обучение использует `dwh_staging.stg_orders` (с fallback для bootstrap окружений). Для production рекомендуется явный переход на curated/marts источники.

## MLflow и артефакты

Tracking URI, имя эксперимента и модели берутся из переменных окружения (`docker-compose.yml`, DAG `dag_ml_train_spark`).
