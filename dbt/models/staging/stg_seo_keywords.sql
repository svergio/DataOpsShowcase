{{ config(
    materialized='view',
    tags=['staging', 'seo']
) }}

WITH src AS (
    SELECT
        keyword_id,
        keyword,
        keyword_category,
        target_url,
        search_volume,
        competition_score,
        cpc_estimate,
        currency,
        current_rank,
        target_rank,
        is_tracked,
        created_at,
        updated_at,
        ingested_at,
        source_run_id
    FROM {{ source('raw', 'oltp_seo_keywords') }}
),
ranked AS (
    SELECT
        s.*,
        ROW_NUMBER() OVER (
            PARTITION BY keyword_id
            ORDER BY ingested_at DESC
        ) AS rn
    FROM src s
    WHERE keyword_id IS NOT NULL
),
latest AS (
    SELECT
        CAST(keyword_id AS TEXT)                               AS keyword_bk,
        LOWER(NULLIF(TRIM(keyword), ''))                       AS keyword,
        NULLIF(TRIM(keyword_category), '')                    AS keyword_category,
        target_url,
        search_volume,
        competition_score,
        cpc_estimate,
        currency,
        current_rank,
        target_rank,
        COALESCE(is_tracked, TRUE)                             AS is_tracked,
        COALESCE(updated_at, created_at)                        AS record_effective_at,
        ingested_at                                             AS load_dts,
        COALESCE(NULLIF(source_run_id, ''), 'oltp_postgres')   AS record_source
    FROM ranked
    WHERE rn = 1
)
SELECT
    {{ generate_hash_key(['keyword_bk']) }}                    AS hub_key,
    keyword_bk,
    keyword,
    keyword_category,
    target_url,
    search_volume,
    competition_score,
    cpc_estimate,
    currency,
    current_rank,
    target_rank,
    is_tracked,
    record_effective_at,
    load_dts,
    record_effective_at                                       AS effective_from,
    record_source,
    {{ generate_hashdiff([
        'keyword',
        'keyword_category',
        'target_url',
        'search_volume',
        'competition_score',
        'cpc_estimate',
        'currency',
        'current_rank',
        'target_rank',
        'is_tracked'
    ]) }}                                                     AS hashdiff
FROM latest
