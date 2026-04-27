-- SCD2 invariant: consecutive versions touch (effective_to of v_n equals effective_from of v_(n+1)).
WITH ordered AS (
    SELECT
        hub_key,
        effective_from,
        effective_to,
        LEAD(effective_from) OVER (PARTITION BY hub_key ORDER BY effective_from ASC) AS next_eff_from
    FROM {{ ref('sat_customer_details') }}
)
SELECT
    hub_key,
    effective_from,
    effective_to,
    next_eff_from
FROM ordered
WHERE next_eff_from IS NOT NULL
  AND effective_to IS DISTINCT FROM next_eff_from
