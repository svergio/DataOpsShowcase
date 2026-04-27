# MinIO: структура объектов (Mermaid)

**Зачем:** понять, как **файловый сырой слой** устроен в bucket (S3-совместимый API), до того как Airflow/Spark заберут данные в БД.

**Bucket** `MINIO_BUCKET_RAW` (часто `techmart-data`) и **префиксы** задаются в [generators/common/config.py](../../generators/common/config.py). Периодическая выгрузка в объекты зависит от `GENERATOR_MINIO_BATCH_TICKS` и логики [generators/generator.py](../../generators/generator.py).

**См. также:** [../Generators.md](../Generators.md).

```mermaid
erDiagram
    BUCKET ||--o{ PAYMENTS_OBJECT : contains
    BUCKET ||--o{ RETURNS_OBJECT : contains
    BUCKET ||--o{ CATALOG_OBJECT : contains

    PAYMENTS_OBJECT ||--|{ PAYMENT_RECORD : "json-lines"
    RETURNS_OBJECT ||--|{ RETURN_RECORD : "csv-rows"
    CATALOG_OBJECT ||--|{ CATALOG_RECORD : "csv-rows"

    BUCKET {
        string name "techmart-data"
        string region "us-east-1"
    }

    PAYMENTS_OBJECT {
        string path "raw/payments/YYYY/MM/DD/payments_TS.jsonl"
        string content_type "application/x-ndjson"
        int records_per_file "40-80"
    }

    RETURNS_OBJECT {
        string path "raw/returns/YYYY/MM/DD/returns_TS.csv"
        string content_type "text/csv"
        int records_per_file "5-20"
    }

    CATALOG_OBJECT {
        string path "raw/product_catalog/YYYY/MM/DD/catalog_update_TS.csv"
        string content_type "text/csv"
        int records_per_file "<=50"
    }

    PAYMENT_RECORD {
        string event_id
        string event_type "PAYMENT_*"
        bigint payment_id
        bigint order_id
        string transaction_id
        decimal amount
        string currency
        string payment_method
        string gateway
        string status
        bigint timestamp_ms
    }

    RETURN_RECORD {
        string return_id
        bigint order_id
        bigint product_id
        string return_reason
        int quantity
        decimal refund_amount
        string currency
        string status
        string requested_at
        string notes
    }

    CATALOG_RECORD {
        bigint product_id
        bigint seller_id
        string product_name
        string brand
        string category
        decimal price
        string currency
        int stock
        boolean is_active
        string updated_at
    }
```

## Партиционирование

- Префиксы: `raw/payments`, `raw/returns`, `raw/product_catalog`.
- Файлы партиционируются по дате (UTC) `YYYY/MM/DD`.
- Имена файлов содержат timestamp `YYYYMMDD_HHMMSS` для идемпотентности.

## Связь с другими источниками

- `payment_id` и `order_id` совпадают с записями из OLTP (`orders.order_id`)
  и Kafka-топиком `${KAFKA_TOPIC_PAYMENTS}`.
- `product_id` ссылается на `products.product_id` (OLTP).
- Файлы caталога — снимки изменений по части `products`.
