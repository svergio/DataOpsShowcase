{{ config(
    materialized='materialized_view',
    on_configuration_change='apply',
    persist_docs={'relation': false, 'columns': false},
    tags=['serving', 'customer_360'],
    indexes=[
        {'columns': ['customer_hub_key'], 'unique': True},
        {'columns': ['customer_segment']},
        {'columns': ['email_domain']}
    ]
) }}

{# Customer 360 — denormalised; customer attributes are masked / hashed only. #}
WITH cust AS (
    SELECT
        customer_hub_key,
        customer_bk,
        customer_hash,
        masked_email,
        masked_name,
        registered_at,
        email_domain,
        is_email_valid,
        customer_segment,
        spend_90d,
        order_count_90d
    FROM {{ ref('dim_customers') }}
),
order_summary AS (
    SELECT
        customer_hub_key,
        COUNT(*)                                              AS lifetime_orders,
        SUM(total_amount)                                     AS lifetime_gross,
        SUM(CASE WHEN payment_state = 'fully_paid' THEN total_amount ELSE 0 END) AS lifetime_paid,
        AVG(total_amount)                                     AS lifetime_aov,
        MAX(order_ts)                                         AS last_order_ts,
        MIN(order_ts)                                         AS first_order_ts,
        SUM(CASE WHEN is_high_value THEN 1 ELSE 0 END)        AS high_value_orders
    FROM {{ ref('fct_orders') }}
    WHERE customer_hub_key IS NOT NULL
    GROUP BY customer_hub_key
),
payment_summary AS (
    SELECT
        fo.customer_hub_key,
        SUM(CASE WHEN fp.status = 'success' THEN fp.amount ELSE 0 END) AS lifetime_payments,
        COUNT(*) FILTER (WHERE fp.status = 'success')                  AS successful_payments,
        COUNT(*) FILTER (WHERE fp.status = 'failed')                   AS failed_payments
    FROM {{ ref('fct_payments') }} fp
    INNER JOIN {{ ref('fct_orders') }} fo
            ON fo.order_hub_key = fp.order_hub_key
    WHERE fo.customer_hub_key IS NOT NULL
    GROUP BY fo.customer_hub_key
)
SELECT
    c.customer_hub_key,
    c.customer_bk,
    c.customer_hash,
    c.masked_email,
    c.masked_name,
    c.registered_at,
    c.email_domain,
    c.is_email_valid,
    c.customer_segment,
    c.spend_90d,
    c.order_count_90d,
    COALESCE(os.lifetime_orders, 0)         AS lifetime_orders,
    COALESCE(os.lifetime_gross, 0)          AS lifetime_gross,
    COALESCE(os.lifetime_paid, 0)          AS lifetime_paid,
    os.lifetime_aov                         AS lifetime_aov,
    os.last_order_ts                        AS last_order_ts,
    os.first_order_ts                       AS first_order_ts,
    COALESCE(os.high_value_orders, 0)       AS high_value_orders,
    COALESCE(ps.lifetime_payments, 0)       AS lifetime_payments,
    COALESCE(ps.successful_payments, 0)     AS successful_payments,
    COALESCE(ps.failed_payments, 0)         AS failed_payments,
    NOW()                                   AS view_refreshed_at
FROM cust c
LEFT JOIN order_summary   os ON os.customer_hub_key = c.customer_hub_key
LEFT JOIN payment_summary ps ON ps.customer_hub_key = c.customer_hub_key
