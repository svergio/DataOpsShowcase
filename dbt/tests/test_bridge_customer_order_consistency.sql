-- Bridge consistency: every bridge row's link_key/customer_hub_key/order_hub_key triple must
-- match a row in the underlying link_customer_order, which in turn must point to existing hubs.
WITH bridge AS (
    SELECT bridge_key, link_key, customer_hub_key, order_hub_key
    FROM {{ ref('bridge_customer_order') }}
),
violations AS (
    SELECT b.*
    FROM bridge b
    LEFT JOIN {{ ref('link_customer_order') }} l
           ON l.link_key = b.link_key
          AND l.customer_hub_key = b.customer_hub_key
          AND l.order_hub_key    = b.order_hub_key
    WHERE l.link_key IS NULL
)
SELECT * FROM violations
