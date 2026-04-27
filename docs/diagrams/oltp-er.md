# OLTP ER Diagram (Mermaid)

Source: `services/postgres/init/02_oltp_schema.sql` (фактическая схема контейнера `postgres_oltp`).
Соответствует ему генератор `generators/generator.py`.

```mermaid
erDiagram
    USERS ||--o{ ORDERS : places
    SELLERS ||--o{ PRODUCTS : sells
    PRODUCTS ||--o{ ORDER_ITEMS : included_in
    ORDERS ||--o{ ORDER_ITEMS : contains

    USERS {
        bigserial user_id PK
        text email "UNIQUE"
        text full_name
        timestamptz created_at
    }

    SELLERS {
        bigserial seller_id PK
        text seller_name
        numeric rating "(3,2)"
        timestamptz created_at
    }

    PRODUCTS {
        bigserial product_id PK
        bigint seller_id FK
        text sku "UNIQUE"
        text product_name
        text category
        numeric price "(12,2)"
        boolean is_active
        timestamptz created_at
    }

    ORDERS {
        bigserial order_id PK
        bigint user_id FK
        timestamptz order_ts
        text status "PENDING/CONFIRMED/SHIPPED/DELIVERED/CANCELLED"
        char currency_code "(3)"
        numeric total_amount "(12,2)"
    }

    ORDER_ITEMS {
        bigserial order_item_id PK
        bigint order_id FK
        bigint product_id FK
        int quantity "> 0"
        numeric unit_price "(12,2)"
    }
```

## Логические связи и cardinality

- `users 1 -- 0..N orders`: пользователь может иметь множество заказов.
- `sellers 1 -- 0..N products`: продавец публикует много товаров.
- `orders 1 -- 1..N order_items`: каждый заказ имеет хотя бы одну позицию.
- `products 1 -- 0..N order_items`: товар может попадать в множество позиций заказов.

## Источник данных

- Заполнение справочников (`users`, `sellers`, `products`) — на старте генератора (seed).
- Заказы и позиции — каждые `GENERATOR_TICK_SECONDS` секунд, объёмом
  `GENERATOR_ORDERS_PER_TICK_MIN..MAX`.
