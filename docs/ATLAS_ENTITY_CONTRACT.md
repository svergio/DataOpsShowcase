# Контракт сущностей Atlas (канонический `qualifiedName`)

Все публикуемые сущности должны содержать стабильный `qualifiedName` в `attributes`, чтобы идемпотентные прогоны могли пропускать уже существующие объекты (см. `entity_publish.py`). Используйте UTF-8 идентификаторы и избегайте случайных пробелов.

Шаблоны (`dataops_net` соответствует имени сети Docker Compose):

| Домен | `typeName` (базовый) | Шаблон `qualifiedName` |
|--------|------------------|------------------------|
| JDBC / Postgres БД (в Atlas как типы `hive_*`; не Apache Hive) | `hive_db` | `{database}@{cluster}`, например `techmart_oltp@dataops` |
| JDBC / Postgres таблица | `hive_table` | `{database}.{schema}.{table}@{cluster}` |
| Kafka topic | `kafka_topic` | `kafka://{cluster_id}@{network}/{topic_name}` |
| Debezium connector | `Process` | `debezium://{cluster_id}@{network}/{connector_slug}` |
| MinIO / S3 логический объект | `Process` | `s3://{endpoint}/{bucket}#{prefix}@{network}` |
| Spark job | `Process` | `spark://{cluster_id}@{job_logical_id}@{script_hint}` |
| Superset metadata app | `Process` | `business://superset/superset@{metadb_logical}` |
| dbt dev / CI | `Process` | `dbt://{project}/{node_id}@{cluster}` |

## Обязательные атрибуты по типам

- **`Process`**: `name`, `qualifiedName`, опционально `description`
- **`kafka_topic`**: `name`, `topic`, `qualifiedName`, `uri` (брокерский URI вида `kafka://kafka:9092/{topic}`)
- **`hive_db`**: `name`, `qualifiedName`, `clusterName` (должен соответствовать части после `@` в `qualifiedName`)
- **`hive_table`**: `name`, `qualifiedName`; `relationshipAttributes.db.uniqueAttributes.qualifiedName` должен совпасть с `qualifiedName` одного из `hive_db` **в этом же YAML-файле** (между файлами каталог Atlas не проверяется локально).

## Валидация YAML

`entity_publish.py` отклоняет дубли пар `(typeName, qualifiedName)`, проверяет обязательные атрибуты (`kafka_topic` включает `uri`) и согласованность `hive_table` → `hive_db` внутри одного файла.
