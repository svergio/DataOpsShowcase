{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key='bridge_key',
    tags=['vault', 'bdv', 'bridge'],
    indexes=[
        {'columns': ['bridge_key'], 'unique': True},
        {'columns': ['customer_hub_key']},
        {'columns': ['order_hub_key']}
    ]
) }}

{# Bridge for customer<->order: flattens link_customer_order with both hubs.
   Used by marts to avoid a 4-way join (link + 2 hubs + sat) on every query. #}
WITH base AS (
    SELECT
        l.link_key,
        l.customer_hub_key,
        l.order_hub_key,
        l.load_dts,
        l.record_source
    FROM {{ ref('link_customer_order') }} l
    INNER JOIN {{ ref('hub_customers') }} hc ON hc.hub_key = l.customer_hub_key
    INNER JOIN {{ ref('hub_orders') }}    ho ON ho.hub_key = l.order_hub_key
)
SELECT
    {{ generate_hash_key(['link_key', 'customer_hub_key', 'order_hub_key']) }} AS bridge_key,
    link_key,
    customer_hub_key,
    order_hub_key,
    load_dts,
    record_source
FROM base
{% if is_incremental() %}
WHERE load_dts >= (SELECT COALESCE(MAX(load_dts) - INTERVAL '7 day', '1970-01-01'::TIMESTAMPTZ) FROM {{ this }})
{% endif %}
