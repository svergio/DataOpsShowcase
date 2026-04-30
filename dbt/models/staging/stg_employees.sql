{{ config(
    materialized='view',
    tags=['staging', 'employees']
) }}

WITH src AS (
    SELECT
        employee_id,
        employee_number,
        first_name,
        last_name,
        email,
        department,
        job_title,
        level,
        manager_id,
        hire_date,
        termination_date,
        employment_status,
        location,
        remote_status,
        salary,
        currency,
        created_at,
        updated_at,
        ingested_at,
        source_run_id
    FROM {{ source('raw', 'oltp_employees') }}
),
ranked AS (
    SELECT
        s.*,
        ROW_NUMBER() OVER (
            PARTITION BY employee_id
            ORDER BY ingested_at DESC
        ) AS rn
    FROM src s
    WHERE employee_id IS NOT NULL
),
latest AS (
    SELECT
        UPPER(NULLIF(TRIM(employee_number), ''))             AS employee_bk,
        NULLIF(TRIM(first_name), '')                         AS first_name,
        NULLIF(TRIM(last_name), '')                          AS last_name,
        LOWER(NULLIF(TRIM(email), ''))                       AS email,
        NULLIF(TRIM(department), '')                         AS department,
        NULLIF(TRIM(job_title), '')                         AS job_title,
        level,
        manager_id,
        hire_date,
        termination_date,
        NULLIF(TRIM(employment_status), '')                  AS employment_status,
        location,
        remote_status,
        salary,
        currency,
        COALESCE(updated_at, created_at)                     AS record_effective_at,
        ingested_at                                           AS load_dts,
        COALESCE(NULLIF(source_run_id, ''), 'oltp_postgres') AS record_source
    FROM ranked
    WHERE rn = 1
)
SELECT
    {{ generate_hash_key(['employee_bk']) }}                 AS hub_key,
    employee_bk,
    first_name,
    last_name,
    email,
    department,
    job_title,
    level,
    manager_id,
    hire_date,
    termination_date,
    employment_status,
    location,
    remote_status,
    salary,
    currency,
    record_effective_at,
    load_dts,
    record_effective_at                                     AS effective_from,
    record_source,
    {{ generate_hashdiff([
        'first_name',
        'last_name',
        'email',
        'department',
        'job_title',
        'level',
        'manager_id',
        'hire_date',
        'termination_date',
        'employment_status',
        'location',
        'remote_status',
        'salary',
        'currency'
    ]) }}                                                   AS hashdiff
FROM latest
