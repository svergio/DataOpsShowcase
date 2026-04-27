{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key=['order_date', 'currency'],
    on_schema_change='append_new_columns',
    tags=['marts', 'fact', 'daily'],
    indexes=[
        {'columns': ['order_date']},
        {'columns': ['order_date', 'currency'], 'unique': True}
    ]
) }}

{# Pre-aggregated daily sales fact. Uses fct_orders (already on PIT/Bridge/BDV). #}
WITH base AS (
    SELECT
        order_date,
        currency,
        COUNT(*)                                                  AS order_count,
        SUM(total_amount)                                         AS gross_sales,
        SUM(CASE WHEN payment_state = 'fully_paid' THEN total_amount ELSE 0 END) AS paid_sales,
        SUM(CASE WHEN payment_state = 'unpaid'      THEN total_amount ELSE 0 END) AS unpaid_sales,
        SUM(total_quantity)                                       AS total_quantity,
        AVG(total_amount)                                         AS avg_order_value,
        SUM(CASE WHEN is_high_value THEN 1 ELSE 0 END)            AS high_value_orders
    FROM {{ ref('fct_orders') }}
    WHERE order_date IS NOT NULL
    GROUP BY order_date, currency
)
SELECT
    base.order_date,
    base.currency,
    base.order_count,
    base.gross_sales,
    base.paid_sales,
    base.unpaid_sales,
    base.total_quantity,
    base.avg_order_value,
    base.high_value_orders,
    NOW() AS mart_load_dts
FROM base
{% if is_incremental() %}
WHERE base.order_date >= (SELECT COALESCE(MAX(order_date) - INTERVAL '7 day', '1970-01-01'::DATE) FROM {{ this }})
{% endif %}
