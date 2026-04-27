{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key=['hub_key', 'as_of_date'],
    tags=['vault', 'bdv', 'pit'],
    indexes=[
        {'columns': ['hub_key', 'as_of_date'], 'unique': True},
        {'columns': ['as_of_date']}
    ]
) }}

{# Point-in-Time table for customers.
   Daily grain. For each (customer hub_key, as_of_date) it records pointers to the
   active versions of every contributing satellite at the END of that day, allowing
   downstream marts to join PIT once and resolve all satellites in O(N) instead of
   running per-satellite scd2 lookups. #}
WITH spine AS (
    SELECT generate_series(
        date_trunc('day', NOW()) - INTERVAL '180 day',
        date_trunc('day', NOW()),
        INTERVAL '1 day'
    ) AS as_of_date
),
hubs AS (
    SELECT hub_key
    FROM {{ ref('hub_customers') }}
),
hub_x_dates AS (
    SELECT h.hub_key, s.as_of_date
    FROM hubs h
    CROSS JOIN spine s
)
SELECT
    hd.hub_key,
    hd.as_of_date,
    sat_cd.load_dts                AS sat_customer_details_load_dts,
    sat_cd.hashdiff                AS sat_customer_details_hashdiff,
    sat_cd.effective_from          AS sat_customer_details_effective_from,
    NOW()                          AS pit_load_dts
FROM hub_x_dates hd
LEFT JOIN LATERAL (
    SELECT s.load_dts, s.hashdiff, s.effective_from
    FROM {{ ref('sat_customer_details') }} s
    WHERE s.hub_key = hd.hub_key
      AND s.effective_from <= (hd.as_of_date + INTERVAL '1 day' - INTERVAL '1 second')
      AND (s.effective_to IS NULL OR s.effective_to > (hd.as_of_date + INTERVAL '1 day' - INTERVAL '1 second'))
    ORDER BY s.effective_from DESC, s.load_dts DESC
    LIMIT 1
) sat_cd ON TRUE
{% if is_incremental() %}
WHERE hd.as_of_date >= (SELECT COALESCE(MAX(as_of_date) - INTERVAL '7 day', '1970-01-01'::DATE) FROM {{ this }})
{% endif %}
