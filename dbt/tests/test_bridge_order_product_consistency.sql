WITH bridge AS (
    SELECT bridge_key, link_key, order_hub_key, product_hub_key
    FROM {{ ref('bridge_order_product') }}
),
violations AS (
    SELECT b.*
    FROM bridge b
    LEFT JOIN {{ ref('link_order_product') }} l
           ON l.link_key = b.link_key
          AND l.order_hub_key   = b.order_hub_key
          AND l.product_hub_key = b.product_hub_key
    WHERE l.link_key IS NULL
)
SELECT * FROM violations
