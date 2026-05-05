{{ config(
    materialized='incremental',
    incremental_strategy='append',
    unique_key=['hub_key', 'load_dts'],
    on_schema_change='append_new_columns',
    tags=['vault', 'bdv', 'satellite', 'scd2'],
    post_hook=[
        "{{ scd2_recompute_timeline() }}"
    ],
    indexes=[
        {'columns': ['hub_key']},
        {'columns': ['hub_key', 'effective_from'], 'unique': True}
    ]
) }}

{# Business satellite: rules on anonymized customer sat (masked_email domain only). #}
WITH raw_sat AS (
    SELECT
        s.hub_key,
        s.masked_email,
        s.masked_name,
        s.registered_at,
        s.load_dts,
        s.effective_from,
        s.is_current,
        s.record_source
    FROM {{ ref('sat_customer_details') }} s
    WHERE s.is_current = TRUE
),
spend_90d AS (
    SELECT
        l.customer_hub_key AS hub_key,
        SUM(sos.total_amount) AS total_spend_90d,
        COUNT(DISTINCT l.order_hub_key) AS order_count_90d
    FROM {{ ref('bridge_customer_order') }} l
    INNER JOIN {{ ref('sat_order_status') }} sos
            ON sos.hub_key = l.order_hub_key
           AND sos.is_current = TRUE
    WHERE sos.order_ts >= NOW() - INTERVAL '90 day'
    GROUP BY l.customer_hub_key
),
enriched AS (
    SELECT
        rs.hub_key,
        rs.masked_email,
        rs.masked_name,
        rs.registered_at,
        SPLIT_PART(rs.masked_email, '@', 2)                                  AS email_domain,
        (rs.masked_email ~* '^[A-Za-z0-9.*_%-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$') AS is_email_valid,
        COALESCE(s.total_spend_90d, 0)                                AS spend_90d,
        COALESCE(s.order_count_90d, 0)                                AS order_count_90d,
        CASE
            WHEN COALESCE(s.total_spend_90d, 0) >= 5000 THEN 'platinum'
            WHEN COALESCE(s.total_spend_90d, 0) >= 1000 THEN 'gold'
            WHEN COALESCE(s.total_spend_90d, 0) >= 200  THEN 'silver'
            ELSE 'bronze'
        END                                                           AS customer_segment,
        rs.load_dts,
        rs.effective_from,
        COALESCE(rs.record_source, 'bdv_customer_business')           AS record_source
    FROM raw_sat rs
    LEFT JOIN spend_90d s ON s.hub_key = rs.hub_key
),
hashed AS (
    SELECT
        e.*,
        {{ generate_hashdiff([
            'email_domain',
            'is_email_valid',
            'customer_segment',
            'spend_90d',
            'order_count_90d'
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
    h.email_domain,
    h.is_email_valid,
    h.customer_segment,
    h.spend_90d,
    h.order_count_90d
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
