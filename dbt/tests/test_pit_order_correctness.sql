WITH pit AS (
    SELECT
        hub_key,
        as_of_date,
        sat_order_status_load_dts,
        sat_order_status_effective_from
    FROM {{ ref('pit_order') }}
),
violations AS (
    SELECT
        p.hub_key,
        p.as_of_date,
        p.sat_order_status_load_dts,
        p.sat_order_status_effective_from,
        s.effective_to AS sat_effective_to
    FROM pit p
    LEFT JOIN {{ ref('sat_order_status') }} s
        ON s.hub_key = p.hub_key
       AND s.load_dts = p.sat_order_status_load_dts
       AND s.effective_from = p.sat_order_status_effective_from
    WHERE p.sat_order_status_load_dts IS NOT NULL
      AND (
            s.hub_key IS NULL
         OR s.effective_from > (p.as_of_date + INTERVAL '1 day' - INTERVAL '1 second')
         OR (s.effective_to IS NOT NULL AND s.effective_to <= (p.as_of_date + INTERVAL '1 day' - INTERVAL '1 second'))
      )
)
SELECT * FROM violations
