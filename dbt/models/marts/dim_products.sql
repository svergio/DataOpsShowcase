{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key='product_hub_key',
    on_schema_change='append_new_columns',
    tags=['marts', 'dim'],
    indexes=[
        {'columns': ['product_hub_key'], 'unique': True},
        {'columns': ['category']}
    ]
) }}

WITH p AS (
    SELECT
        hub_key,
        sku,
        product_name,
        category,
        price,
        is_active,
        seller_bk,
        effective_from,
        load_dts
    FROM {{ ref('sat_product_attributes') }}
    WHERE is_current = TRUE
),
hub AS (
    SELECT hub_key, business_key
    FROM {{ ref('hub_products') }}
)
SELECT
    h.hub_key            AS product_hub_key,
    h.business_key       AS product_bk,
    p.sku                AS sku,
    p.product_name       AS product_name,
    p.category           AS category,
    p.price              AS price,
    p.is_active          AS is_active,
    p.seller_bk          AS seller_bk,
    p.effective_from     AS effective_from,
    p.load_dts           AS rdv_load_dts,
    NOW()                AS mart_load_dts
FROM hub h
LEFT JOIN p ON p.hub_key = h.hub_key
{% if is_incremental() %}
WHERE COALESCE(p.load_dts, NOW()) >=
      (SELECT COALESCE(MAX(rdv_load_dts) - INTERVAL '7 day', '1970-01-01'::TIMESTAMPTZ) FROM {{ this }})
{% endif %}
