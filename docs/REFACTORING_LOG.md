# Лог реорганизации монорепозитория

## Ключевые переносы

| Было | Стало |
| --- | --- |
| `services/spark_jobs/preprocess_orders_payments.py` | `spark/jobs/preprocess_orders_payments.py` |
| `services/spark_jobs/train_order_value_model.py` | `ml/training/train_order_value_model.py` |
| `services/spark/conf/` | `spark/conf/` |
| `data_generators/*` | `generators/*` (`common/`, `kafka/`) |
| `docs/Pipelines.md` | `docs/PIPELINES.md` |

## Удалённые/устаревшие пути

- `services/spark_jobs/`
- `services/spark/`
- `data_generators/`
- `workflows/`
- `spark_jobs/` (пустой placeholder)

## Новые файлы и директории

- `spark/common/lib_runtime.py`, `spark/common/spark_session.py`
- `generators/kafka/orders_generator.py`, `payments_generator.py`, `clickstream_generator.py`
- `ml/configs/training_default.yaml`, `configs/spark/preprocess_default.yaml`
- `docs/README.md`, `docs/ARCHITECTURE.md`, `docs/ML.md`, `docs/SETUP.md`
- `requirements/dev.txt`, `pytest.ini`, `tests/unit/*`

## Проверка

- `pytest tests/unit` проходит после `pip install -r requirements/dev.txt`.

## Оставшиеся зазоры

- Можно подключить чтение `configs/spark/*.yaml` напрямую внутри Spark job.
- Каталог `streaming/` не консолидирован с `services/kafka/`.
