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

{# Point-in-Time table for orders.
   Daily grain. For each (order hub_key, as_of_date) returns pointers to the active
   sat_order_status row. Joins to sat_order_enriched (BDV) are added by marts. #}
WITH spine AS (
    SELECT generate_series(
        date_trunc('day', NOW()) - INTERVAL '180 day',
        date_trunc('day', NOW()),
        INTERVAL '1 day'
    ) AS as_of_date
),
hubs AS (
    SELECT hub_key
    FROM {{ ref('hub_orders') }}
),
hub_x_dates AS (
    SELECT h.hub_key, s.as_of_date
    FROM hubs h
    CROSS JOIN spine s
)
SELECT
    hd.hub_key,
    hd.as_of_date,
    sat_os.load_dts                AS sat_order_status_load_dts,
    sat_os.hashdiff                AS sat_order_status_hashdiff,
    sat_os.effective_from          AS sat_order_status_effective_from,
    NOW()                          AS pit_load_dts
FROM hub_x_dates hd
LEFT JOIN LATERAL (
    SELECT s.load_dts, s.hashdiff, s.effective_from
    FROM {{ ref('sat_order_status') }} s
    WHERE s.hub_key = hd.hub_key
      AND s.effective_from <= (hd.as_of_date + INTERVAL '1 day' - INTERVAL '1 second')
      AND (s.effective_to IS NULL OR s.effective_to > (hd.as_of_date + INTERVAL '1 day' - INTERVAL '1 second'))
    ORDER BY s.effective_from DESC, s.load_dts DESC
    LIMIT 1
) sat_os ON TRUE
{% if is_incremental() %}
WHERE hd.as_of_date >= (SELECT COALESCE(MAX(as_of_date) - INTERVAL '7 day', '1970-01-01'::DATE) FROM {{ this }})
{% endif %}
