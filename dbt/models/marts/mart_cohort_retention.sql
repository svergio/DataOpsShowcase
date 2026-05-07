{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key=['cohort_month', 'activity_date'],
    on_schema_change='append_new_columns',
    tags=['marts', 'business_kpis'],
    indexes=[
        {'columns': ['cohort_month']},
        {'columns': ['activity_date']},
        {'columns': ['days_since_first_order']}
    ]
) }}

WITH customer_orders AS (
    SELECT
        customer_hub_key,
        order_date
    FROM {{ ref('fct_orders') }}
    WHERE customer_hub_key IS NOT NULL
      AND order_date IS NOT NULL
),
first_orders AS (
    SELECT
        customer_hub_key,
        MIN(order_date) AS first_order_date,
        DATE_TRUNC('month', MIN(order_date))::date AS cohort_month
    FROM customer_orders
    GROUP BY customer_hub_key
),
activity AS (
    SELECT DISTINCT
        customer_hub_key,
        order_date AS activity_date
    FROM customer_orders
),
cohort_sizes AS (
    SELECT
        cohort_month,
        COUNT(*) AS cohort_size
    FROM first_orders
    GROUP BY cohort_month
),
fact AS (
    SELECT
        f.cohort_month,
        a.activity_date,
        (a.activity_date - f.first_order_date) AS days_since_first_order,
        COUNT(DISTINCT a.customer_hub_key) AS active_users
    FROM activity a
    JOIN first_orders f
      ON f.customer_hub_key = a.customer_hub_key
    WHERE a.activity_date >= f.first_order_date
    GROUP BY f.cohort_month, a.activity_date, (a.activity_date - f.first_order_date)
)
SELECT
    fact.cohort_month,
    fact.activity_date,
    fact.days_since_first_order,
    fact.active_users,
    cs.cohort_size,
    CASE
        WHEN cs.cohort_size = 0 THEN NULL
        ELSE fact.active_users::numeric / cs.cohort_size
    END AS retention_rate,
    CASE
        WHEN fact.days_since_first_order IN (1, 7, 30, 90) THEN fact.days_since_first_order
        ELSE NULL
    END AS canonical_day_marker,
    NOW() AS mart_load_dts
FROM fact
JOIN cohort_sizes cs
  ON cs.cohort_month = fact.cohort_month
{% if is_incremental() %}
WHERE fact.activity_date >= (
    SELECT COALESCE(MAX(activity_date) - INTERVAL '30 day', '1970-01-01'::date) FROM {{ this }}
)
{% endif %}
