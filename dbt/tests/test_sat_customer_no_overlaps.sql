-- SCD2 invariant: no overlapping versions per hub_key in sat_customer_details.
WITH timeline_overlaps AS (
    SELECT
        a.hub_key,
        a.effective_from,
        a.effective_to,
        b.effective_from AS b_effective_from,
        b.effective_to   AS b_effective_to
    FROM {{ ref('sat_customer_details') }} a
    INNER JOIN {{ ref('sat_customer_details') }} b
            ON a.hub_key = b.hub_key
           AND a.effective_from < b.effective_from
    WHERE COALESCE(a.effective_to, '9999-12-31'::TIMESTAMPTZ) > b.effective_from
)
SELECT * FROM timeline_overlaps
