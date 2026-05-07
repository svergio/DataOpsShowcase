{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key=['metric_date', 'category', 'seller_bk'],
    on_schema_change='append_new_columns',
    tags=['marts', 'business_kpis'],
    indexes=[
        {'columns': ['metric_date']},
        {'columns': ['category']},
        {'columns': ['seller_bk']}
    ]
) }}

WITH line_items AS (
    SELECT
        bop.order_hub_key,
        bop.product_hub_key,
        bop.total_quantity,
        bop.total_line_amount
    FROM {{ ref('bridge_order_product') }} bop
),
orders AS (
    SELECT
        order_hub_key,
        order_date,
        payment_state
    FROM {{ ref('fct_orders') }}
    WHERE order_date IS NOT NULL
),
products AS (
    SELECT
        product_hub_key,
        COALESCE(category, 'unknown') AS category,
        COALESCE(seller_bk, 'unknown') AS seller_bk
    FROM {{ ref('dim_products') }}
),
agg AS (
    SELECT
        o.order_date AS metric_date,
        p.category,
        p.seller_bk,
        COUNT(DISTINCT o.order_hub_key) AS orders_count,
        SUM(li.total_quantity) AS items_sold,
        SUM(li.total_line_amount) AS gross_revenue,
        SUM(CASE WHEN o.payment_state = 'fully_paid' THEN li.total_line_amount ELSE 0 END) AS paid_revenue
    FROM line_items li
    JOIN orders o
      ON o.order_hub_key = li.order_hub_key
    JOIN products p
      ON p.product_hub_key = li.product_hub_key
    GROUP BY o.order_date, p.category, p.seller_bk
)
SELECT
    metric_date,
    category,
    seller_bk,
    orders_count,
    items_sold,
    gross_revenue,
    paid_revenue,
    CASE WHEN orders_count = 0 THEN NULL ELSE gross_revenue / orders_count END AS avg_order_revenue,
    NULL::numeric AS returns_rate,
    NOW() AS mart_load_dts
FROM agg
{% if is_incremental() %}
WHERE metric_date >= (
    SELECT COALESCE(MAX(metric_date) - INTERVAL '7 day', '1970-01-01'::date) FROM {{ this }}
)
{% endif %}
