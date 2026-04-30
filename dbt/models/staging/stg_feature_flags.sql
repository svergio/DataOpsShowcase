{{ config(
    materialized='view',
    tags=['staging', 'feature_flags']
) }}

WITH src AS (
    SELECT
        flag_id,
        flag_key,
        flag_name,
        description,
        is_enabled,
        rollout_percentage,
        targeting_rules,
        created_at,
        updated_at,
        ingested_at,
        source_run_id
    FROM {{ source('raw', 'oltp_feature_flags') }}
),
ranked AS (
    SELECT
        s.*,
        ROW_NUMBER() OVER (
            PARTITION BY flag_id
            ORDER BY ingested_at DESC
        ) AS rn
    FROM src s
    WHERE flag_id IS NOT NULL
),
latest AS (
    SELECT
        LOWER(NULLIF(TRIM(flag_key), ''))                      AS flag_bk,
        NULLIF(TRIM(flag_name), '')                          AS flag_name,
        description,
        COALESCE(is_enabled, FALSE)                          AS is_enabled,
        rollout_percentage,
        targeting_rules,
        COALESCE(updated_at, created_at)                     AS record_effective_at,
        ingested_at                                           AS load_dts,
        COALESCE(NULLIF(source_run_id, ''), 'oltp_postgres') AS record_source
    FROM ranked
    WHERE rn = 1
      AND flag_key IS NOT NULL
)
SELECT
    {{ generate_hash_key(['flag_bk']) }}                     AS hub_key,
    flag_bk,
    flag_name,
    description,
    is_enabled,
    rollout_percentage,
    targeting_rules,
    record_effective_at,
    load_dts,
    record_effective_at                                     AS effective_from,
    record_source,
    {{ generate_hashdiff([
        'flag_name',
        'description',
        'is_enabled',
        'rollout_percentage',
        'targeting_rules'
    ]) }}                                                   AS hashdiff
FROM latest
