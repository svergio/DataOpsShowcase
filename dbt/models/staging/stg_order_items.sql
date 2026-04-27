{{ config(
    materialized='view',
    tags=['staging', 'order_items']
) }}

{# Staging view for order line items, used to build link_order_product.
   Latest snapshot per order_item_id. #}
WITH src AS (
    SELECT
        order_item_id,
        order_id,
        product_id,
        quantity,
        unit_price,
        ingested_at,
        source_run_id
    FROM {{ source('raw', 'oltp_order_items') }}
),
ranked AS (
    SELECT
        s.*,
        ROW_NUMBER() OVER (
            PARTITION BY order_item_id
            ORDER BY ingested_at DESC
        ) AS rn
    FROM src s
    WHERE order_item_id IS NOT NULL
)
SELECT
    CAST(order_item_id AS TEXT)                              AS order_item_bk,
    CAST(order_id      AS TEXT)                              AS order_bk,
    CAST(product_id    AS TEXT)                              AS product_bk,
    quantity                                                 AS quantity,
    unit_price                                               AS unit_price,
    (quantity * unit_price)                                  AS line_amount,
    ingested_at                                              AS load_dts,
    COALESCE(NULLIF(source_run_id, ''), 'oltp_postgres')    AS record_source
FROM ranked
WHERE rn = 1
