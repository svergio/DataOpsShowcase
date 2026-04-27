{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key='payment_hub_key',
    on_schema_change='append_new_columns',
    tags=['marts', 'fact'],
    indexes=[
        {'columns': ['payment_hub_key'], 'unique': True},
        {'columns': ['order_hub_key']},
        {'columns': ['payment_date']},
        {'columns': ['status']}
    ]
) }}

{# fct_payments — one row per payment. Joins via link_order_payment to fetch order_hub_key.
   Uses raw sat_payment_details because BDV business satellite for payments is not yet defined;
   payment status enrichment lives in sat_order_enriched. #}
WITH lop AS (
    SELECT DISTINCT
        payment_hub_key,
        order_hub_key,
        load_dts AS link_load_dts
    FROM {{ ref('link_order_payment') }}
),
sp AS (
    SELECT
        hub_key   AS payment_hub_key,
        amount,
        currency,
        payment_method,
        status,
        decline_reason,
        transaction_id,
        effective_from AS payment_ts,
        load_dts
    FROM {{ ref('sat_payment_details') }}
    WHERE is_current = TRUE
),
hubs AS (
    SELECT hub_key, business_key AS payment_bk
    FROM {{ ref('hub_payments') }}
)
SELECT
    h.hub_key                          AS payment_hub_key,
    h.payment_bk                       AS payment_bk,
    l.order_hub_key                    AS order_hub_key,
    sp.amount                          AS amount,
    sp.currency                        AS currency,
    sp.payment_method                  AS payment_method,
    sp.status                          AS status,
    sp.decline_reason                  AS decline_reason,
    sp.transaction_id                  AS transaction_id,
    sp.payment_ts                      AS payment_ts,
    DATE(sp.payment_ts)                AS payment_date,
    sp.load_dts                        AS rdv_load_dts,
    NOW()                              AS mart_load_dts
FROM hubs h
LEFT JOIN lop l  ON l.payment_hub_key = h.hub_key
LEFT JOIN sp     ON sp.payment_hub_key = h.hub_key
{% if is_incremental() %}
WHERE COALESCE(sp.load_dts, NOW()) >=
      (SELECT COALESCE(MAX(rdv_load_dts) - INTERVAL '7 day', '1970-01-01'::TIMESTAMPTZ) FROM {{ this }})
{% endif %}
