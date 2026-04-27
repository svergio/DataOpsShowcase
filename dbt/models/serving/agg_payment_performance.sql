{{ config(
    materialized='table',
    tags=['serving', 'pre_aggregation'],
    indexes=[
        {'columns': ['payment_date']},
        {'columns': ['payment_date', 'payment_method', 'currency'], 'unique': True}
    ]
) }}

{# Daily payment performance metrics by payment method. #}
WITH base AS (
    SELECT
        payment_date,
        payment_method,
        currency,
        COUNT(*)                                                     AS attempts,
        COUNT(*) FILTER (WHERE status = 'success')                   AS successes,
        COUNT(*) FILTER (WHERE status IN ('failed', 'declined'))     AS failures,
        SUM(CASE WHEN status = 'success' THEN amount ELSE 0 END)     AS paid_amount,
        SUM(CASE WHEN status <> 'success' THEN amount ELSE 0 END)    AS rejected_amount
    FROM {{ ref('fct_payments') }}
    WHERE payment_date IS NOT NULL
      AND payment_method IS NOT NULL
    GROUP BY payment_date, payment_method, currency
)
SELECT
    payment_date,
    payment_method,
    currency,
    attempts,
    successes,
    failures,
    paid_amount,
    rejected_amount,
    CASE WHEN attempts = 0 THEN NULL ELSE successes::NUMERIC / attempts END AS success_rate,
    NOW() AS aggregated_at
FROM base
