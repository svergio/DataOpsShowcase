{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key=['metric_date', 'currency'],
    on_schema_change='append_new_columns',
    tags=['marts', 'business_kpis'],
    indexes=[
        {'columns': ['metric_date']},
        {'columns': ['currency']},
        {'columns': ['metric_date', 'currency'], 'unique': True}
    ]
) }}

WITH orders AS (
    SELECT
        order_hub_key,
        customer_hub_key,
        order_date,
        currency,
        total_amount,
        paid_amount,
        payment_state
    FROM {{ ref('fct_orders') }}
    WHERE order_date IS NOT NULL
),
first_orders AS (
    SELECT
        customer_hub_key,
        MIN(order_date) AS first_order_date
    FROM orders
    GROUP BY customer_hub_key
),
daily AS (
    SELECT
        o.order_date AS metric_date,
        o.currency,
        COUNT(DISTINCT o.order_hub_key) AS orders_count,
        COUNT(DISTINCT o.customer_hub_key) AS buyers_count,
        COUNT(DISTINCT CASE WHEN o.order_date = f.first_order_date THEN o.customer_hub_key END) AS new_buyers_count,
        COUNT(DISTINCT CASE WHEN o.order_date > f.first_order_date THEN o.customer_hub_key END) AS repeat_buyers_count,
        SUM(o.total_amount) AS gmv,
        SUM(COALESCE(o.paid_amount, o.total_amount)) AS net_revenue,
        SUM(CASE WHEN o.payment_state = 'fully_paid' THEN 1 ELSE 0 END) AS fully_paid_orders_count,
        SUM(CASE WHEN o.payment_state = 'partially_paid' THEN 1 ELSE 0 END) AS partially_paid_orders_count,
        SUM(CASE WHEN o.payment_state = 'unpaid' THEN 1 ELSE 0 END) AS unpaid_orders_count
    FROM orders o
    LEFT JOIN first_orders f
      ON f.customer_hub_key = o.customer_hub_key
    GROUP BY o.order_date, o.currency
)
SELECT
    metric_date,
    currency,
    orders_count,
    buyers_count,
    new_buyers_count,
    repeat_buyers_count,
    gmv,
    net_revenue,
    CASE WHEN orders_count = 0 THEN NULL ELSE gmv / orders_count END AS aov,
    fully_paid_orders_count,
    partially_paid_orders_count,
    unpaid_orders_count,
    0::numeric AS returns_amount,
    0::numeric AS discounts_amount,
    0::numeric AS commissions_amount,
    NOW() AS mart_load_dts
FROM daily
{% if is_incremental() %}
WHERE metric_date >= (
    SELECT COALESCE(MAX(metric_date) - INTERVAL '7 day', '1970-01-01'::date) FROM {{ this }}
)
{% endif %}
