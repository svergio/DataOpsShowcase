-- Business rule: dim_customers.customer_segment must be one of the allowed values when set.
SELECT customer_hub_key, customer_segment
FROM {{ ref('dim_customers') }}
WHERE customer_segment IS NOT NULL
  AND customer_segment NOT IN ('platinum', 'gold', 'silver', 'bronze')
