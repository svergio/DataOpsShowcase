{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key=['metric_date', 'channel'],
    on_schema_change='append_new_columns',
    tags=['marts', 'business_kpis'],
    indexes=[
        {'columns': ['metric_date']},
        {'columns': ['channel']}
    ]
) }}

WITH campaigns AS (
    SELECT
        COALESCE(start_date, CURRENT_DATE)::date AS metric_date,
        COALESCE(NULLIF(TRIM(channel), ''), 'unknown') AS channel,
        COALESCE(NULLIF(TRIM(status), ''), 'unknown') AS campaign_status,
        COALESCE(budget, 0)::numeric AS budget
    FROM {{ ref('stg_marketing_campaigns') }}
),
agg AS (
    SELECT
        metric_date,
        channel,
        COUNT(*) AS campaigns_count,
        SUM(budget) AS planned_budget,
        SUM(CASE WHEN campaign_status = 'active' THEN 1 ELSE 0 END) AS active_campaigns_count
    FROM campaigns
    GROUP BY metric_date, channel
)
SELECT
    metric_date,
    channel,
    campaigns_count,
    active_campaigns_count,
    planned_budget,
    NULL::bigint AS attributed_orders_count,
    NULL::numeric AS attributed_revenue,
    NULL::numeric AS roas,
    NULL::numeric AS conversion_rate,
    NOW() AS mart_load_dts
FROM agg
{% if is_incremental() %}
WHERE metric_date >= (
    SELECT COALESCE(MAX(metric_date) - INTERVAL '30 day', '1970-01-01'::date) FROM {{ this }}
)
{% endif %}
