{{ config(
    materialized='view',
    tags=['staging', 'customers']
) }}

{# Latest row per customer from Spark-populated staging.stg_customers (anonymized). #}
WITH src AS (
    SELECT
        customer_id,
        customer_hash,
        masked_email,
        masked_name,
        registered_at,
        effective_from AS load_dts,
        source_record_hash
    FROM {{ source('staging_pipeline', 'stg_customers') }}
    WHERE customer_id IS NOT NULL
),
ranked AS (
    SELECT
        s.*,
        ROW_NUMBER() OVER (
            PARTITION BY customer_id
            ORDER BY load_dts DESC
        ) AS rn
    FROM src s
),
latest AS (
    SELECT
        CAST(customer_id AS TEXT)                                AS customer_bk,
        customer_hash,
        masked_email,
        masked_name,
        registered_at,
        load_dts,
        'spark_preprocess'                                        AS record_source
    FROM ranked
    WHERE rn = 1
)
SELECT
    {{ generate_hash_key(['customer_bk']) }} AS hub_key,
    customer_bk,
    customer_hash,
    masked_email,
    masked_name,
    registered_at,
    load_dts,
    load_dts                                  AS effective_from,
    record_source,
    {{ generate_hashdiff([
        'customer_hash',
        'masked_email',
        'masked_name',
        'registered_at'
    ]) }}                                     AS hashdiff
FROM latest
