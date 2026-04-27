{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key='bridge_key',
    tags=['vault', 'bdv', 'bridge'],
    indexes=[
        {'columns': ['bridge_key'], 'unique': True},
        {'columns': ['order_hub_key']},
        {'columns': ['product_hub_key']}
    ]
) }}

{# Bridge for order<->product: combines link_order_product with both hubs and
   pre-aggregates line-level metrics from stg_order_items so mart fact tables
   can fan-in cheaply. #}
WITH line_agg AS (
    SELECT
        order_bk,
        product_bk,
        SUM(quantity)    AS total_quantity,
        SUM(line_amount) AS total_line_amount,
        MIN(load_dts)    AS first_load_dts,
        MAX(load_dts)    AS last_load_dts,
        MIN(record_source) AS record_source
    FROM {{ ref('stg_order_items') }}
    GROUP BY order_bk, product_bk
),
joined AS (
    SELECT
        l.link_key,
        l.order_hub_key,
        l.product_hub_key,
        la.total_quantity,
        la.total_line_amount,
        la.last_load_dts AS load_dts,
        la.record_source
    FROM {{ ref('link_order_product') }} l
    INNER JOIN {{ ref('hub_orders') }}   ho ON ho.hub_key = l.order_hub_key
    INNER JOIN {{ ref('hub_products') }} hp ON hp.hub_key = l.product_hub_key
    INNER JOIN line_agg la
            ON la.order_bk   = ho.business_key
           AND la.product_bk = hp.business_key
)
SELECT
    {{ generate_hash_key(['link_key', 'order_hub_key', 'product_hub_key']) }} AS bridge_key,
    link_key,
    order_hub_key,
    product_hub_key,
    total_quantity,
    total_line_amount,
    load_dts,
    record_source
FROM joined
{% if is_incremental() %}
WHERE load_dts >= (SELECT COALESCE(MAX(load_dts) - INTERVAL '7 day', '1970-01-01'::TIMESTAMPTZ) FROM {{ this }})
{% endif %}
