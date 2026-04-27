{{ config(
    materialized='view',
    tags=['staging', 'payments']
) }}

{# Staging view for payments.
   Source: raw.kafka_payments (event-driven). MinIO files-landed payments
   from staging.stg_minio_payments are UNIONed in to merge file-based and
   stream-based feeds.
   - canonicalises payment status to lower-case
   - keeps the latest event per payment_id (by event_ts then ingested_at)
   - emits hash_key (BK = payment_bk) + hashdiff for SCD2 downstream #}
WITH kafka_src AS (
    SELECT
        CAST(payment_id AS TEXT)                                  AS payment_bk,
        CAST(order_id   AS TEXT)                                  AS order_bk,
        transaction_id,
        amount,
        UPPER(NULLIF(TRIM(currency), ''))                         AS currency,
        LOWER(NULLIF(TRIM(payment_method), ''))                   AS payment_method,
        LOWER(NULLIF(TRIM(status), ''))                           AS status,
        decline_reason,
        event_ts,
        ingested_at                                               AS load_dts,
        'kafka_payments'                                          AS record_source
    FROM {{ source('raw', 'kafka_payments') }}
    WHERE payment_id IS NOT NULL
),
minio_src AS (
    SELECT
        CAST(payment_id AS TEXT)                                  AS payment_bk,
        CAST(order_id   AS TEXT)                                  AS order_bk,
        CAST(NULL AS TEXT)                                        AS transaction_id,
        amount,
        UPPER(NULLIF(TRIM(currency), ''))                         AS currency,
        CAST(NULL AS TEXT)                                        AS payment_method,
        LOWER(NULLIF(TRIM(status), ''))                           AS status,
        CAST(NULL AS TEXT)                                        AS decline_reason,
        event_ts,
        loaded_at                                                 AS load_dts,
        'minio_files'                                             AS record_source
    FROM {{ source('staging_pipeline', 'stg_minio_payments') }}
    WHERE payment_id IS NOT NULL
),
unioned AS (
    SELECT * FROM kafka_src
    UNION ALL
    SELECT * FROM minio_src
),
ranked AS (
    SELECT
        u.*,
        ROW_NUMBER() OVER (
            PARTITION BY payment_bk
            ORDER BY event_ts DESC NULLS LAST, load_dts DESC
        ) AS rn
    FROM unioned u
),
latest AS (
    SELECT *
    FROM ranked
    WHERE rn = 1
)
SELECT
    {{ generate_hash_key(['payment_bk']) }}   AS hub_key,
    payment_bk,
    order_bk,
    transaction_id,
    amount,
    currency,
    payment_method,
    status,
    decline_reason,
    event_ts,
    load_dts,
    COALESCE(event_ts, load_dts)              AS effective_from,
    record_source,
    {{ generate_hashdiff([
        'amount',
        'currency',
        'payment_method',
        'status',
        'decline_reason',
        'transaction_id'
    ]) }}                                     AS hashdiff
FROM latest
