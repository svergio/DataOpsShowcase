{{ config(
    materialized='view',
    tags=['staging', 'orders']
) }}

{# Staging view for orders.
   - keeps the latest snapshot per (order_id) from raw.oltp_orders
   - normalises currency (upper) and status (lower)
   - emits hash_key, hashdiff for satellite/hub downstream #}
WITH src AS (
    SELECT
        order_id,
        user_id,
        order_ts,
        status,
        currency_code,
        total_amount,
        ingested_at,
        source_run_id
    FROM {{ source('raw', 'oltp_orders') }}
),
ranked AS (
    SELECT
        s.*,
        ROW_NUMBER() OVER (
            PARTITION BY order_id
            ORDER BY ingested_at DESC
        ) AS rn
    FROM src s
    WHERE order_id IS NOT NULL
),
latest AS (
    SELECT
        CAST(order_id AS TEXT)                                AS order_bk,
        CAST(user_id  AS TEXT)                                AS customer_bk,
        order_ts,
        LOWER(NULLIF(TRIM(status), ''))                       AS status,
        UPPER(NULLIF(TRIM(currency_code), ''))                AS currency,
        total_amount                                          AS total_amount,
        ingested_at                                           AS load_dts,
        COALESCE(NULLIF(source_run_id, ''), 'oltp_postgres')  AS record_source
    FROM ranked
    WHERE rn = 1
)
SELECT
    {{ generate_hash_key(['order_bk']) }}     AS hub_key,
    order_bk,
    customer_bk,
    order_ts,
    status,
    currency,
    total_amount,
    load_dts,
    load_dts                                  AS effective_from,
    record_source,
    {{ generate_hashdiff([
        'status',
        'currency',
        'total_amount',
        'order_ts'
    ]) }}                                     AS hashdiff
FROM latest
