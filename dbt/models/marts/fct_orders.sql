{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key='order_hub_key',
    on_schema_change='append_new_columns',
    tags=['marts', 'fact'],
    indexes=[
        {'columns': ['order_hub_key'], 'unique': True},
        {'columns': ['customer_hub_key']},
        {'columns': ['order_date']},
        {'columns': ['payment_state']}
    ]
) }}

{# fct_orders — fact at the grain of one row per order.
   Joins:
     hub_orders -> bridge_customer_order (cheap, no scd2) -> sat_order_enriched (BDV) -> sat_order_status (RDV currency).
   Built using BDV bridge instead of direct link+hub joins for cheaper fan-in. #}
WITH bridge AS (
    SELECT DISTINCT
        order_hub_key,
        customer_hub_key
    FROM {{ ref('bridge_customer_order') }}
),
oe AS (
    SELECT
        hub_key            AS order_hub_key,
        status,
        currency,
        total_amount,
        order_ts,
        is_high_value,
        total_items,
        total_quantity,
        has_successful_payment,
        paid_amount,
        payment_state,
        load_dts
    FROM {{ ref('sat_order_enriched') }}
    WHERE is_current = TRUE
),
hubs AS (
    SELECT hub_key, business_key AS order_bk
    FROM {{ ref('hub_orders') }}
)
SELECT
    h.hub_key                          AS order_hub_key,
    h.order_bk                         AS order_bk,
    b.customer_hub_key                 AS customer_hub_key,
    oe.status                          AS status,
    oe.currency                        AS currency,
    oe.total_amount                    AS total_amount,
    oe.is_high_value                   AS is_high_value,
    oe.total_items                     AS total_items,
    oe.total_quantity                  AS total_quantity,
    oe.has_successful_payment          AS has_successful_payment,
    oe.paid_amount                     AS paid_amount,
    oe.payment_state                   AS payment_state,
    oe.order_ts                        AS order_ts,
    DATE(oe.order_ts)                  AS order_date,
    oe.load_dts                        AS bdv_load_dts,
    NOW()                              AS mart_load_dts
FROM hubs h
LEFT JOIN bridge b ON b.order_hub_key = h.hub_key
LEFT JOIN oe       ON oe.order_hub_key = h.hub_key
{% if is_incremental() %}
WHERE COALESCE(oe.load_dts, NOW()) >=
      (SELECT COALESCE(MAX(bdv_load_dts) - INTERVAL '7 day', '1970-01-01'::TIMESTAMPTZ) FROM {{ this }})
{% endif %}
