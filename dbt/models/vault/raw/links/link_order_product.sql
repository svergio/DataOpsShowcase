{{ config(
    materialized='incremental',
    incremental_strategy='append',
    unique_key='link_key',
    on_schema_change='append_new_columns',
    tags=['vault', 'rdv', 'link'],
    indexes=[
        {'columns': ['link_key'], 'unique': True},
        {'columns': ['order_hub_key']},
        {'columns': ['product_hub_key']}
    ]
) }}

WITH src AS (
    SELECT
        order_bk,
        product_bk,
        load_dts,
        record_source
    FROM {{ ref('stg_order_items') }}
    WHERE order_bk   IS NOT NULL
      AND product_bk IS NOT NULL
),
deduped AS (
    SELECT
        order_bk,
        product_bk,
        MIN(load_dts) AS load_dts,
        MIN(record_source) AS record_source
    FROM src
    GROUP BY order_bk, product_bk
)
SELECT
    {{ generate_hash_key(['order_bk', 'product_bk']) }} AS link_key,
    {{ generate_hash_key(['order_bk']) }}               AS order_hub_key,
    {{ generate_hash_key(['product_bk']) }}             AS product_hub_key,
    load_dts,
    record_source
FROM deduped d
{% if is_incremental() %}
WHERE NOT EXISTS (
    SELECT 1
    FROM {{ this }} t
    WHERE t.link_key = {{ generate_hash_key(['order_bk', 'product_bk']) }}
)
{% endif %}
