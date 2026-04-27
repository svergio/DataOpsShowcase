{{ config(
    materialized='table',
    tags=['serving', 'pre_aggregation'],
    indexes=[
        {'columns': ['order_date']},
        {'columns': ['order_date', 'currency'], 'unique': True}
    ]
) }}

{# Daily sales pre-aggregation. Fully derived from fct_daily_sales but adds rolling
   metrics (moving avg, week-over-week growth) for BI. #}
WITH base AS (
    SELECT
        order_date,
        currency,
        order_count,
        gross_sales,
        paid_sales,
        unpaid_sales,
        total_quantity,
        avg_order_value,
        high_value_orders
    FROM {{ ref('fct_daily_sales') }}
),
windowed AS (
    SELECT
        b.*,
        AVG(gross_sales)  OVER (
            PARTITION BY currency
            ORDER BY order_date
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ) AS gross_sales_7d_ma,
        AVG(gross_sales)  OVER (
            PARTITION BY currency
            ORDER BY order_date
            ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
        ) AS gross_sales_30d_ma,
        LAG(gross_sales, 7) OVER (
            PARTITION BY currency
            ORDER BY order_date
        ) AS gross_sales_lag_7d
    FROM base b
)
SELECT
    order_date,
    currency,
    order_count,
    gross_sales,
    paid_sales,
    unpaid_sales,
    total_quantity,
    avg_order_value,
    high_value_orders,
    gross_sales_7d_ma,
    gross_sales_30d_ma,
    gross_sales_lag_7d,
    CASE
        WHEN gross_sales_lag_7d IS NULL OR gross_sales_lag_7d = 0 THEN NULL
        ELSE (gross_sales - gross_sales_lag_7d) / gross_sales_lag_7d
    END AS wow_growth,
    NOW() AS aggregated_at
FROM windowed
