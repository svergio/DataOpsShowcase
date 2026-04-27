{{ config(
    materialized='view',
    tags=['staging', 'customers']
) }}

{# Staging view for customers.
   - de-duplicates raw.oltp_users by user_id keeping the latest snapshot
   - normalises email/full_name (lower, trim) and casts to canonical types
   - emits load_dts, record_source, hash_key, hashdiff for downstream DV2 layer #}
WITH src AS (
    SELECT
        user_id,
        email,
        full_name,
        created_at,
        ingested_at,
        source_run_id
    FROM {{ source('raw', 'oltp_users') }}
),
ranked AS (
    SELECT
        s.*,
        ROW_NUMBER() OVER (
            PARTITION BY user_id
            ORDER BY ingested_at DESC
        ) AS rn
    FROM src s
    WHERE user_id IS NOT NULL
),
latest AS (
    SELECT
        CAST(user_id AS TEXT)                                AS customer_bk,
        LOWER(NULLIF(TRIM(email), ''))                        AS email,
        NULLIF(TRIM(full_name), '')                           AS full_name,
        created_at                                            AS registered_at,
        ingested_at                                           AS load_dts,
        COALESCE(NULLIF(source_run_id, ''), 'oltp_postgres') AS record_source
    FROM ranked
    WHERE rn = 1
)
SELECT
    {{ generate_hash_key(['customer_bk']) }} AS hub_key,
    customer_bk,
    email,
    full_name,
    registered_at,
    load_dts,
    load_dts                                  AS effective_from,
    record_source,
    {{ generate_hashdiff([
        'email',
        'full_name',
        'registered_at'
    ]) }}                                     AS hashdiff
FROM latest
