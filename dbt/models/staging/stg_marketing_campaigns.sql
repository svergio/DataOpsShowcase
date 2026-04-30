{{ config(
    materialized='view',
    tags=['staging', 'campaigns']
) }}

WITH src AS (
    SELECT
        campaign_id,
        campaign_name,
        campaign_type,
        channel,
        budget,
        currency,
        start_date,
        end_date,
        target_audience,
        status,
        created_by,
        created_at,
        updated_at,
        ingested_at,
        source_run_id
    FROM {{ source('raw', 'oltp_marketing_campaigns') }}
),
ranked AS (
    SELECT
        s.*,
        ROW_NUMBER() OVER (
            PARTITION BY campaign_id
            ORDER BY ingested_at DESC
        ) AS rn
    FROM src s
    WHERE campaign_id IS NOT NULL
),
latest AS (
    SELECT
        CAST(campaign_id AS TEXT)                              AS campaign_bk,
        NULLIF(TRIM(campaign_name), '')                         AS campaign_name,
        NULLIF(TRIM(campaign_type), '')                        AS campaign_type,
        NULLIF(TRIM(channel), '')                               AS channel,
        budget,
        currency,
        start_date,
        end_date,
        target_audience,
        NULLIF(TRIM(status), '')                                AS status,
        created_by,
        COALESCE(updated_at, created_at)                        AS record_effective_at,
        ingested_at                                             AS load_dts,
        COALESCE(NULLIF(source_run_id, ''), 'oltp_postgres')   AS record_source
    FROM ranked
    WHERE rn = 1
)
SELECT
    {{ generate_hash_key(['campaign_bk']) }}                  AS hub_key,
    campaign_bk,
    campaign_name,
    campaign_type,
    channel,
    budget,
    currency,
    start_date,
    end_date,
    target_audience,
    status,
    created_by,
    record_effective_at,
    load_dts,
    record_effective_at                                       AS effective_from,
    record_source,
    {{ generate_hashdiff([
        'campaign_name',
        'campaign_type',
        'channel',
        'budget',
        'currency',
        'start_date',
        'end_date',
        'status',
        'target_audience',
        'created_by'
    ]) }}                                                     AS hashdiff
FROM latest
