{{ config(
    materialized='view',
    tags=['staging', 'kafka_extensions']
) }}

WITH src AS (
    SELECT
        topic,
        partition_id,
        kafka_offset,
        domain_code,
        event_id,
        event_type,
        payload,
        event_ts,
        ingested_at
    FROM {{ source('raw', 'kafka_extension_events') }}
),
dedup AS (
    SELECT
        s.*,
        ROW_NUMBER() OVER (
            PARTITION BY topic, partition_id, kafka_offset
            ORDER BY ingested_at DESC
        ) AS rn
    FROM src s
),
shaped AS (
    SELECT
        topic,
        partition_id,
        kafka_offset,
        domain_code,
        event_id,
        event_type,
        payload,
        event_ts,
        ingested_at,
        COALESCE(
            NULLIF(TRIM(event_id), ''),
            topic || ':' || partition_id::text || ':' || kafka_offset::text
        ) AS event_bk
    FROM dedup
    WHERE rn = 1
)
SELECT
    {{ generate_hash_key(['event_bk']) }}                   AS hub_key,
    event_bk,
    topic,
    partition_id,
    kafka_offset,
    domain_code,
    event_type,
    payload,
    COALESCE(event_ts, ingested_at)                         AS record_effective_at,
    ingested_at                                             AS load_dts,
    COALESCE(event_ts, ingested_at)                         AS effective_from,
    'kafka.extension_events'::text                          AS record_source,
    {{ generate_hashdiff([
        'domain_code',
        'event_type',
        'payload'
    ]) }}                                                   AS hashdiff
FROM shaped
