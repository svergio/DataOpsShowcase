# Kafka Topic Model (Mermaid)

Топики, в которые пишет `data_generator`, и связанные с ними сущности.
Имена и партиционирование задаются через `.env`.

```mermaid
erDiagram
    CLICKSTREAM_TOPIC ||--|{ CLICKSTREAM_EVENT : "session-keyed"
    ORDERS_TOPIC ||--|{ ORDER_EVENT : "order_id-keyed"
    PAYMENTS_TOPIC ||--|{ PAYMENT_EVENT : "payment_id-keyed"
    SHIPMENTS_TOPIC ||--|{ SHIPMENT_EVENT : "shipment_id-keyed"

    ORDER_EVENT ||--o{ PAYMENT_EVENT : "order_id"
    ORDER_EVENT ||--o{ SHIPMENT_EVENT : "order_id"
    ORDER_EVENT ||--|{ ORDER_ITEM : "embeds"

    CLICKSTREAM_TOPIC {
        string name "techmart.events.clickstream"
        int partitions "12"
        int retention_days "7"
    }
    ORDERS_TOPIC {
        string name "techmart.events.orders"
        int partitions "8"
        int retention_days "30"
    }
    PAYMENTS_TOPIC {
        string name "techmart.payments.transactions"
        int partitions "6"
        int retention_days "30"
    }
    SHIPMENTS_TOPIC {
        string name "techmart.shipments.tracking"
        int partitions "4"
        int retention_days "30"
    }

    CLICKSTREAM_EVENT {
        string event_id PK
        string event_type
        bigint timestamp_ms
        string session_id "partition key"
        bigint customer_id
        bigint product_id
        string category
        string page_url
        string device_type
        string country_code
    }
    ORDER_EVENT {
        string event_id PK
        string event_type
        bigint order_id "partition key"
        string order_number
        bigint customer_id
        string country_code
        string timestamp_iso
        string previous_status
        string new_status
        decimal total_amount
        string currency
        int items_count
    }
    ORDER_ITEM {
        bigint product_id
        string sku
        int quantity
        decimal unit_price
        decimal subtotal
        string category
    }
    PAYMENT_EVENT {
        string event_id PK
        string event_type
        bigint payment_id "partition key"
        bigint order_id
        string transaction_id
        decimal amount
        string currency
        string payment_method
        string gateway
        string status
        string decline_reason
        int risk_score
        bigint timestamp_ms
    }
    SHIPMENT_EVENT {
        string event_id PK
        string event_type
        bigint shipment_id "partition key"
        bigint order_id
        string tracking_number
        string carrier
        string status
        string country
        string timestamp_iso
    }
```

## Соглашения

- Сериализация: JSON (UTF-8) с `linger.ms=50`, `compression.type=lz4`,
  `enable.idempotence=true`.
- Ключи: для clickstream — `session_id`, для остальных топиков — id основной сущности.
- Все события несут `event_id` (UUID-производный) для дедупликации downstream.
- Идемпотентность: события могут повторяться, но `event_id` уникален в пределах потока.

## Связь между топиками

- `ORDER_EVENT.order_id` ↔ `PAYMENT_EVENT.order_id` ↔ `SHIPMENT_EVENT.order_id`.
- `CLICKSTREAM_EVENT.customer_id` ↔ `ORDER_EVENT.customer_id`.
- `ORDER_EVENT.items[*].product_id` ↔ записи в OLTP `products.product_id`.
