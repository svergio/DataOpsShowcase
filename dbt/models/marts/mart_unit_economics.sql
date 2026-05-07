{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key='cohort_month',
    on_schema_change='append_new_columns',
    tags=['marts', 'business_kpis'],
    indexes=[
        {'columns': ['cohort_month'], 'unique': True}
    ]
) }}

WITH users AS (
    SELECT
        customer_hub_key,
        first_order_date,
        ltv_30d,
        ltv_90d,
        ltv_180d,
        ltv_365d,
        revenue_total,
        orders_total
    FROM {{ ref('mart_user_rfm') }}
),
cohorts AS (
    SELECT
        DATE_TRUNC('month', first_order_date)::date AS cohort_month,
        COUNT(*) AS customers_count,
        AVG(ltv_30d) AS avg_ltv_30d,
        AVG(ltv_90d) AS avg_ltv_90d,
        AVG(ltv_180d) AS avg_ltv_180d,
        AVG(ltv_365d) AS avg_ltv_365d,
        AVG(CASE WHEN orders_total = 0 THEN NULL ELSE revenue_total / orders_total END) AS avg_order_margin
    FROM users
    GROUP BY DATE_TRUNC('month', first_order_date)::date
)
SELECT
    cohort_month,
    customers_count,
    avg_ltv_30d,
    avg_ltv_90d,
    avg_ltv_180d,
    avg_ltv_365d,
    NULL::numeric AS avg_cac,
    NULL::numeric AS ltv_cac_ratio,
    NULL::numeric AS payback_months,
    NULL::numeric AS contribution_margin,
    avg_order_margin,
    'CAC/ROAS/payback require attribution and variable-cost sources'::text AS limitations_note,
    NOW() AS mart_load_dts
FROM cohorts
{% if is_incremental() %}
WHERE cohort_month >= (
    SELECT COALESCE(MAX(cohort_month) - INTERVAL '180 day', '1970-01-01'::date) FROM {{ this }}
)
{% endif %}
