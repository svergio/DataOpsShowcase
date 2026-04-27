{{ config(
    materialized='table',
    tags=['serving', 'pre_aggregation'],
    indexes=[
        {'columns': ['order_date', 'customer_segment'], 'unique': True}
    ]
) }}

{# Pre-aggregation: gross revenue per day x customer_segment.
   Useful for segmentation dashboards. #}
WITH joined AS (
    SELECT
        fo.order_date,
        dc.customer_segment,
        fo.currency,
        fo.total_amount,
        fo.payment_state,
        fo.is_high_value
    FROM {{ ref('fct_orders') }} fo
    INNER JOIN {{ ref('dim_customers') }} dc
            ON dc.customer_hub_key = fo.customer_hub_key
    WHERE fo.order_date IS NOT NULL
      AND dc.customer_segment IS NOT NULL
)
SELECT
    order_date,
    customer_segment,
    COUNT(*)                                                  AS order_count,
    SUM(total_amount)                                         AS gross_sales,
    SUM(CASE WHEN payment_state = 'fully_paid' THEN total_amount ELSE 0 END) AS paid_sales,
    SUM(CASE WHEN is_high_value THEN 1 ELSE 0 END)            AS high_value_orders,
    NOW() AS aggregated_at
FROM joined
GROUP BY order_date, customer_segment
