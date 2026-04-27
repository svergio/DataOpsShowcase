WITH timeline_overlaps AS (
    SELECT
        a.hub_key,
        a.effective_from AS a_eff_from,
        a.effective_to   AS a_eff_to,
        b.effective_from AS b_eff_from,
        b.effective_to   AS b_eff_to
    FROM {{ ref('sat_order_status') }} a
    INNER JOIN {{ ref('sat_order_status') }} b
            ON a.hub_key = b.hub_key
           AND a.effective_from < b.effective_from
    WHERE COALESCE(a.effective_to, '9999-12-31'::TIMESTAMPTZ) > b.effective_from
)
SELECT * FROM timeline_overlaps
