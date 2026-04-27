-- SCD2 invariant: each hub_key in sat_customer_details has exactly one is_current=TRUE row.
SELECT hub_key, SUM(CASE WHEN is_current THEN 1 ELSE 0 END) AS current_count
FROM {{ ref('sat_customer_details') }}
GROUP BY hub_key
HAVING SUM(CASE WHEN is_current THEN 1 ELSE 0 END) <> 1
