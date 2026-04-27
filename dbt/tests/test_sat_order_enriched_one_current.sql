SELECT hub_key, SUM(CASE WHEN is_current THEN 1 ELSE 0 END) AS current_count
FROM {{ ref('sat_order_enriched') }}
GROUP BY hub_key
HAVING SUM(CASE WHEN is_current THEN 1 ELSE 0 END) <> 1
