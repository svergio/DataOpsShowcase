{{ config(
    materialized='view',
    tags=['staging', 'gl']
) }}

WITH src AS (
    SELECT
        entry_id,
        entry_date,
        entry_number,
        account_code,
        account_name,
        account_type,
        debit_amount,
        credit_amount,
        currency,
        transaction_type,
        reference_id,
        reference_type,
        description,
        posted_by,
        created_at,
        ingested_at,
        source_run_id
    FROM {{ source('raw', 'oltp_general_ledger') }}
),
ranked AS (
    SELECT
        s.*,
        ROW_NUMBER() OVER (
            PARTITION BY entry_id
            ORDER BY ingested_at DESC
        ) AS rn
    FROM src s
    WHERE entry_id IS NOT NULL
),
latest AS (
    SELECT
        UPPER(NULLIF(TRIM(entry_number), ''))                 AS gl_entry_bk,
        entry_date,
        NULLIF(TRIM(account_code), '')                       AS account_code,
        NULLIF(TRIM(account_name), '')                       AS account_name,
        NULLIF(TRIM(account_type), '')                       AS account_type,
        COALESCE(debit_amount, 0)                            AS debit_amount,
        COALESCE(credit_amount, 0)                            AS credit_amount,
        currency,
        NULLIF(TRIM(transaction_type), '')                   AS transaction_type,
        reference_id,
        NULLIF(TRIM(reference_type), '')                     AS reference_type,
        description,
        posted_by,
        created_at                                            AS record_effective_at,
        ingested_at                                           AS load_dts,
        COALESCE(NULLIF(source_run_id, ''), 'oltp_postgres') AS record_source
    FROM ranked
    WHERE rn = 1
)
SELECT
    {{ generate_hash_key(['gl_entry_bk']) }}                 AS hub_key,
    gl_entry_bk,
    entry_date,
    account_code,
    account_name,
    account_type,
    debit_amount,
    credit_amount,
    currency,
    transaction_type,
    reference_id,
    reference_type,
    description,
    posted_by,
    record_effective_at,
    load_dts,
    record_effective_at                                     AS effective_from,
    record_source,
    {{ generate_hashdiff([
        'entry_date',
        'account_code',
        'account_name',
        'account_type',
        'debit_amount',
        'credit_amount',
        'currency',
        'transaction_type',
        'reference_id',
        'reference_type',
        'description',
        'posted_by'
    ]) }}                                                    AS hashdiff
FROM latest
