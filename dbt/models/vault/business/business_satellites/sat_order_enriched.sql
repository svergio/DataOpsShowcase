{{ config(
    materialized='incremental',
    incremental_strategy='append',
    unique_key=['hub_key', 'load_dts'],
    on_schema_change='append_new_columns',
    tags=['vault', 'bdv', 'business_satellite', 'scd2'],
    post_hook=[
        "{{ scd2_recompute_timeline() }}"
    ],
    indexes=[
        {'columns': ['hub_key']},
        {'columns': ['hub_key', 'effective_from'], 'unique': True}
    ]
) }}

{# Business satellite for orders.
   Enriches raw sat_order_status with:
     * is_high_value flag (>= 1000 in base currency)
     * payment_match: TRUE iff there exists a confirmed payment for this order
     * total_items: line count from bridge_order_product
     * total_quantity: sum of quantities #}
WITH base AS (
    SELECT
        s.hub_key,
        s.status,
        s.currency,
        s.total_amount,
        s.order_ts,
        s.load_dts,
        s.effective_from,
        s.record_source
    FROM {{ ref('sat_order_status') }} s
    WHERE s.is_current = TRUE
),
items AS (
    SELECT
        order_hub_key   AS hub_key,
        SUM(total_quantity) AS total_quantity,
        COUNT(*)            AS total_items
    FROM {{ ref('bridge_order_product') }}
    GROUP BY order_hub_key
),
payments AS (
    SELECT
        l.order_hub_key AS hub_key,
        BOOL_OR(LOWER(sp.status) = 'success') AS has_successful_payment,
        SUM(CASE WHEN LOWER(sp.status) = 'success' THEN sp.amount ELSE 0 END) AS paid_amount
    FROM {{ ref('link_order_payment') }} l
    INNER JOIN {{ ref('sat_payment_details') }} sp
            ON sp.hub_key = l.payment_hub_key
           AND sp.is_current = TRUE
    GROUP BY l.order_hub_key
),
enriched AS (
    SELECT
        b.hub_key,
        b.status,
        b.currency,
        b.total_amount,
        b.order_ts,
        b.load_dts,
        b.effective_from,
        COALESCE(b.record_source, 'bdv_order_enriched') AS record_source,
        (b.total_amount >= 1000)                            AS is_high_value,
        COALESCE(i.total_items, 0)                          AS total_items,
        COALESCE(i.total_quantity, 0)                       AS total_quantity,
        COALESCE(p.has_successful_payment, FALSE)           AS has_successful_payment,
        COALESCE(p.paid_amount, 0)                          AS paid_amount,
        CASE
            WHEN p.has_successful_payment AND ABS(COALESCE(p.paid_amount, 0) - b.total_amount) < 0.01 THEN 'fully_paid'
            WHEN p.has_successful_payment THEN 'partially_paid'
            ELSE 'unpaid'
        END                                                 AS payment_state
    FROM base b
    LEFT JOIN items    i ON i.hub_key = b.hub_key
    LEFT JOIN payments p ON p.hub_key = b.hub_key
),
hashed AS (
    SELECT
        e.*,
        {{ generate_hashdiff([
            'status',
            'currency',
            'total_amount',
            'is_high_value',
            'total_items',
            'total_quantity',
            'has_successful_payment',
            'paid_amount',
            'payment_state'
        ]) }} AS hashdiff
    FROM enriched e
)
SELECT
    h.hub_key,
    h.hashdiff,
    h.load_dts,
    h.effective_from,
    CAST(NULL AS TIMESTAMPTZ)              AS effective_to,
    TRUE                                   AS is_current,
    h.record_source,
    h.status,
    h.currency,
    h.total_amount,
    h.order_ts,
    h.is_high_value,
    h.total_items,
    h.total_quantity,
    h.has_successful_payment,
    h.paid_amount,
    h.payment_state
FROM hashed h
{% if is_incremental() %}
LEFT JOIN LATERAL (
    SELECT t.hashdiff
    FROM {{ this }} t
    WHERE t.hub_key = h.hub_key
      AND t.effective_from <= h.effective_from
    ORDER BY t.effective_from DESC, t.load_dts DESC
    LIMIT 1
) prior_version ON TRUE
LEFT JOIN {{ this }} exact_match
       ON exact_match.hub_key = h.hub_key
      AND exact_match.effective_from = h.effective_from
WHERE exact_match.hub_key IS NULL
  AND (prior_version.hashdiff IS NULL OR prior_version.hashdiff <> h.hashdiff)
{% endif %}
