-- Business rule: if has_successful_payment = TRUE then payment_state must be 'fully_paid' or 'partially_paid'.
SELECT order_hub_key, has_successful_payment, payment_state
FROM {{ ref('fct_orders') }}
WHERE has_successful_payment = TRUE
  AND COALESCE(payment_state, 'unpaid') NOT IN ('fully_paid', 'partially_paid')
