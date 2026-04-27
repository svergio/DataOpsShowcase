{{ config(
    materialized='view',
    tags=['staging', 'products']
) }}

{# Staging view for products.
   - latest snapshot per product_id from raw.oltp_products
   - normalises sku (upper, trim), category (lower)
   - join order_items aggregation is NOT performed here; products are dimensional only #}
WITH src AS (
    SELECT
        product_id,
        seller_id,
        sku,
        product_name,
        category,
        price,
        is_active,
        created_at,
        ingested_at,
        source_run_id
    FROM {{ source('raw', 'oltp_products') }}
),
ranked AS (
    SELECT
        s.*,
        ROW_NUMBER() OVER (
            PARTITION BY product_id
            ORDER BY ingested_at DESC
        ) AS rn
    FROM src s
    WHERE product_id IS NOT NULL
),
latest AS (
    SELECT
        CAST(product_id AS TEXT)                              AS product_bk,
        CAST(seller_id  AS TEXT)                              AS seller_bk,
        UPPER(NULLIF(TRIM(sku), ''))                          AS sku,
        NULLIF(TRIM(product_name), '')                        AS product_name,
        LOWER(NULLIF(TRIM(category), ''))                     AS category,
        price                                                 AS price,
        COALESCE(is_active, FALSE)                            AS is_active,
        created_at                                            AS first_listed_at,
        ingested_at                                           AS load_dts,
        COALESCE(NULLIF(source_run_id, ''), 'oltp_postgres') AS record_source
    FROM ranked
    WHERE rn = 1
)
SELECT
    {{ generate_hash_key(['product_bk']) }}   AS hub_key,
    product_bk,
    seller_bk,
    sku,
    product_name,
    category,
    price,
    is_active,
    first_listed_at,
    load_dts,
    load_dts                                  AS effective_from,
    record_source,
    {{ generate_hashdiff([
        'sku',
        'product_name',
        'category',
        'price',
        'is_active',
        'seller_bk'
    ]) }}                                     AS hashdiff
FROM latest
