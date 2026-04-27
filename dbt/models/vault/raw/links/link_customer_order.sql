{{ config(
    materialized='incremental',
    incremental_strategy='append',
    unique_key='link_key',
    on_schema_change='append_new_columns',
    tags=['vault', 'rdv', 'link'],
    indexes=[
        {'columns': ['link_key'], 'unique': True},
        {'columns': ['customer_hub_key']},
        {'columns': ['order_hub_key']}
    ]
) }}

WITH src AS (
    SELECT
        customer_bk,
        order_bk,
        load_dts,
        record_source
    FROM {{ ref('stg_orders') }}
    WHERE customer_bk IS NOT NULL
      AND order_bk    IS NOT NULL
),
deduped AS (
    SELECT
        customer_bk,
        order_bk,
        MIN(load_dts) AS load_dts,
        MIN(record_source) AS record_source
    FROM src
    GROUP BY customer_bk, order_bk
)
SELECT
    {{ generate_hash_key(['customer_bk', 'order_bk']) }} AS link_key,
    {{ generate_hash_key(['customer_bk']) }}             AS customer_hub_key,
    {{ generate_hash_key(['order_bk']) }}                AS order_hub_key,
    load_dts,
    record_source
FROM deduped d
{% if is_incremental() %}
WHERE NOT EXISTS (
    SELECT 1
    FROM {{ this }} t
    WHERE t.link_key = {{ generate_hash_key(['customer_bk', 'order_bk']) }}
)
{% endif %}
