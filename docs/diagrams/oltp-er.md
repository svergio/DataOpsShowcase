# OLTP: ER-диаграмма (PostgreSQL, Mermaid)

**Зачем:** быстро понять сущности маркетплейса TechMart в транзакционной БД.

**Источник правды по DDL:** [02_oltp_schema.sql](../../services/postgres/init/02_oltp_schema.sql), [02b_oltp_marketing_hr_finance.sql](../../services/postgres/init/02b_oltp_marketing_hr_finance.sql), [02c_oltp_retail_legacy.sql](../../services/postgres/init/02c_oltp_retail_legacy.sql) (ретейл-линия: купоны, софт-кампании, легаси-ключи; контейнер `postgres_oltp` и авто-DDL генератора).

**Генератор:** вставки согласованы с [generators/generator.py](../../generators/generator.py) и [../Generators.md](../Generators.md).

```mermaid
erDiagram
    USERS ||--o{ ORDERS : places
    SELLERS ||--o{ PRODUCTS : sells
    PRODUCTS ||--o{ ORDER_ITEMS : included_in
    ORDERS ||--o{ ORDER_ITEMS : contains
    MARKETING_CAMPAIGNS ||--o{ ORDERS : campaigns_soft

    USERS {
        bigserial user_id PK
        text email "UNIQUE"
        text full_name
        varchar legacy_crm_customer_id "CRM import"
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
        numeric subtotal_before_discount
        numeric discount_amount
        varchar coupon_code
        int campaign_id "soft"
        varchar legacy_campaign_code
        varchar legacy_order_ref
        varchar order_lineage "canonical|legacy_stub"
    }

    ORDER_ITEMS {
        bigserial order_item_id PK
        bigint order_id FK
        bigint product_id FK
        int quantity "> 0"
        numeric unit_price "(12,2)"
    }

    MARKETING_CAMPAIGNS {
        serial campaign_id PK
        varchar campaign_name
        varchar campaign_type
        numeric budget
        date start_date
        date end_date
        jsonb target_audience
        varchar status
    }

    SEO_KEYWORDS {
        serial keyword_id PK
        varchar keyword "UNIQUE"
        varchar keyword_category
        int search_volume
        int current_rank
    }

    EMPLOYEES {
        serial employee_id PK
        varchar department
        varchar level
        int manager_id FK "nullable self-ref"
        date hire_date
        varchar employment_status
    }

    FEATURE_FLAGS {
        serial flag_id PK
        varchar flag_key "UNIQUE"
        int rollout_percentage
        jsonb targeting_rules
    }

    GENERAL_LEDGER {
        bigserial entry_id PK
        date entry_date
        varchar account_code
        varchar account_type "ASSET/REVENUE..."
        numeric debit_amount
        numeric credit_amount
    }
```

Связь **`MARKETING_CAMPAIGNS`** с **`ORDERS`** на диаграмме означает логическую атрибуцию по полю `orders.campaign_id` (soft pointer, **без FK в БД** — безопасно для легаси-бэкфиллов). Часть строк имитирует легаси-слой (`order_lineage = legacy_stub`, текстовые коды кампаний без join).

## Логические связи и cardinality

- `users 1 -- 0..N orders`: пользователь может иметь множество заказов.
- `sellers 1 -- 0..N products`: продавец публикует много товаров.
- `orders 1 -- 1..N order_items`: каждый заказ имеет хотя бы одну позицию.
- `products 1 -- 0..N order_items`: товар может попадать в множество позиций заказов.
- Генератор задаёт **~70%** заказов как «канонических» (скидка и `campaign_id` или чистая корзина согласованы) и **~30%** как `legacy_stub` (пустой `campaign_id`, заполненные `legacy_campaign_code` / POS-референсы).

## Источник данных

- Заполнение справочников (`users`, `sellers`, `products`) — на старте генератора (seed).
- Заказы и позиции — каждые `GENERATOR_TICK_SECONDS` секунд, объёмом
  `GENERATOR_ORDERS_PER_TICK_MIN..MAX`.
