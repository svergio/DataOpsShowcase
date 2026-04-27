{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key='customer_hub_key',
    on_schema_change='append_new_columns',
    tags=['marts', 'dim'],
    indexes=[
        {'columns': ['customer_hub_key'], 'unique': True},
        {'columns': ['customer_segment']},
        {'columns': ['email_domain']}
    ]
) }}

{# dim_customers — current snapshot, sourced from BDV business satellite + raw customer details.
   Marts read BDV (sat_customer_business) + raw sat (for full_name) to avoid
   chasing satellites separately. #}
WITH cust_b AS (
    SELECT
        hub_key,
        email_domain,
        is_email_valid,
        customer_segment,
        spend_90d,
        order_count_90d,
        effective_from,
        load_dts
    FROM {{ ref('sat_customer_business') }}
    WHERE is_current = TRUE
),
cust_raw AS (
    SELECT
        hub_key,
        email,
        full_name,
        registered_at
    FROM {{ ref('sat_customer_details') }}
    WHERE is_current = TRUE
),
hub AS (
    SELECT hub_key, business_key
    FROM {{ ref('hub_customers') }}
)
SELECT
    h.hub_key                          AS customer_hub_key,
    h.business_key                     AS customer_bk,
    cr.email                           AS email,
    cr.full_name                       AS full_name,
    cr.registered_at                   AS registered_at,
    cb.email_domain                    AS email_domain,
    cb.is_email_valid                  AS is_email_valid,
    cb.customer_segment                AS customer_segment,
    cb.spend_90d                       AS spend_90d,
    cb.order_count_90d                 AS order_count_90d,
    cb.effective_from                  AS effective_from,
    cb.load_dts                        AS bdv_load_dts,
    NOW()                              AS mart_load_dts
FROM hub h
LEFT JOIN cust_raw cr ON cr.hub_key = h.hub_key
LEFT JOIN cust_b   cb ON cb.hub_key = h.hub_key
{% if is_incremental() %}
WHERE COALESCE(cb.load_dts, cr.registered_at, NOW()) >=
      (SELECT COALESCE(MAX(bdv_load_dts) - INTERVAL '7 day', '1970-01-01'::TIMESTAMPTZ) FROM {{ this }})
{% endif %}
