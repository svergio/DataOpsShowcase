{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key='customer_hub_key',
    on_schema_change='append_new_columns',
    tags=['marts', 'business_kpis'],
    indexes=[
        {'columns': ['customer_hub_key'], 'unique': True},
        {'columns': ['first_order_date']},
        {'columns': ['last_order_date']}
    ]
) }}

WITH base AS (
    SELECT
        customer_hub_key,
        order_date,
        total_amount
    FROM {{ ref('fct_orders') }}
    WHERE customer_hub_key IS NOT NULL
      AND order_date IS NOT NULL
),
agg AS (
    SELECT
        customer_hub_key,
        MIN(order_date) AS first_order_date,
        MAX(order_date) AS last_order_date,
        COUNT(*) AS orders_total,
        SUM(total_amount) AS revenue_total,
        AVG(total_amount) AS avg_order_value,
        SUM(CASE WHEN order_date >= CURRENT_DATE - INTERVAL '30 day' THEN 1 ELSE 0 END) AS orders_30d,
        SUM(CASE WHEN order_date >= CURRENT_DATE - INTERVAL '90 day' THEN 1 ELSE 0 END) AS orders_90d
    FROM base
    GROUP BY customer_hub_key
),
ltv AS (
    SELECT
        b.customer_hub_key,
        SUM(CASE WHEN b.order_date <= a.first_order_date + INTERVAL '30 day' THEN b.total_amount ELSE 0 END) AS ltv_30d,
        SUM(CASE WHEN b.order_date <= a.first_order_date + INTERVAL '90 day' THEN b.total_amount ELSE 0 END) AS ltv_90d,
        SUM(CASE WHEN b.order_date <= a.first_order_date + INTERVAL '180 day' THEN b.total_amount ELSE 0 END) AS ltv_180d,
        SUM(CASE WHEN b.order_date <= a.first_order_date + INTERVAL '365 day' THEN b.total_amount ELSE 0 END) AS ltv_365d
    FROM base b
    JOIN agg a
      ON a.customer_hub_key = b.customer_hub_key
    GROUP BY b.customer_hub_key
)
SELECT
    a.customer_hub_key,
    a.first_order_date,
    a.last_order_date,
    (CURRENT_DATE - a.last_order_date) AS days_since_last_purchase,
    a.orders_total,
    a.revenue_total,
    a.avg_order_value,
    a.orders_30d,
    a.orders_90d,
    CASE WHEN a.orders_total = 0 THEN NULL ELSE a.revenue_total / a.orders_total END AS revenue_per_order,
    CASE WHEN a.orders_90d = 0 THEN 0 ELSE a.orders_90d::numeric / 90 END AS purchase_frequency_90d,
    l.ltv_30d,
    l.ltv_90d,
    l.ltv_180d,
    l.ltv_365d,
    NOW() AS mart_load_dts
FROM agg a
JOIN ltv l
  ON l.customer_hub_key = a.customer_hub_key
{% if is_incremental() %}
WHERE a.last_order_date >= (
    SELECT COALESCE(MAX(last_order_date) - INTERVAL '30 day', '1970-01-01'::date) FROM {{ this }}
)
{% endif %}
