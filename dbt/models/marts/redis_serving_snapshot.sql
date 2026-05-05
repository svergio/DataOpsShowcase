{{ config(
    materialized='table',
    tags=['marts', 'serving', 'redis'],
    indexes=[
        {'columns': ['metric_key'], 'unique': true}
    ]
) }}

WITH today_sales AS (
    SELECT COALESCE(SUM(gross_sales), 0)::numeric(18,4) AS metric_value_num
    FROM {{ ref('fct_daily_sales') }}
    WHERE order_date = CURRENT_DATE
),
active_customers AS (
    SELECT COUNT(DISTINCT customer_hub_key)::numeric(18,4) AS metric_value_num
    FROM {{ ref('fct_orders') }}
    WHERE order_date >= CURRENT_DATE - INTERVAL '30 day'
),
latest_product_category AS (
    SELECT COALESCE(category, 'unknown')::text AS metric_value_text
    FROM {{ ref('dim_products') }}
    ORDER BY mart_load_dts DESC
    LIMIT 1
)
SELECT
    'daily_sales_gross'::text AS metric_key,
    metric_value_num,
    NULL::text AS metric_value_text,
    'dbt:fct_daily_sales'::text AS source_sql,
    NOW() AS updated_at
FROM today_sales
UNION ALL
SELECT
    'active_customers_30d'::text AS metric_key,
    metric_value_num,
    NULL::text AS metric_value_text,
    'dbt:fct_orders'::text AS source_sql,
    NOW() AS updated_at
FROM active_customers
UNION ALL
SELECT
    'top_product_category_today'::text AS metric_key,
    NULL::numeric(18,4) AS metric_value_num,
    metric_value_text,
    'dbt:dim_products'::text AS source_sql,
    NOW() AS updated_at
FROM latest_product_category
