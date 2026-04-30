{{ config(
    materialized='incremental',
    incremental_strategy='append',
    unique_key=['hub_key', 'load_dts'],
    on_schema_change='append_new_columns',
    tags=['vault', 'rdv', 'satellite', 'scd2'],
    post_hook=[
        "{{ scd2_recompute_timeline() }}"
    ],
    indexes=[
        {'columns': ['hub_key']},
        {'columns': ['hub_key', 'effective_from'], 'unique': True}
    ]
) }}

WITH src AS (
    SELECT
        hub_key,
        hashdiff,
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
        load_dts,
        effective_from,
        record_source
    FROM {{ ref('stg_employees') }}
    WHERE hub_key       IS NOT NULL
      AND hashdiff      IS NOT NULL
      AND effective_from IS NOT NULL
),
deduped AS (
    SELECT *
    FROM (
        SELECT
            s.*,
            ROW_NUMBER() OVER (
                PARTITION BY hub_key, effective_from
                ORDER BY load_dts DESC, hashdiff ASC
            ) AS rn
        FROM src s
    ) t
    WHERE rn = 1
)
SELECT
    d.hub_key,
    d.hashdiff,
    d.load_dts,
    d.effective_from,
    CAST(NULL AS TIMESTAMPTZ) AS effective_to,
    TRUE                      AS is_current,
    d.record_source,
    d.first_name,
    d.last_name,
    d.email,
    d.department,
    d.job_title,
    d.level,
    d.manager_id,
    d.hire_date,
    d.termination_date,
    d.employment_status,
    d.location,
    d.remote_status,
    d.salary,
    d.currency
FROM deduped d
{% if is_incremental() %}
LEFT JOIN LATERAL (
    SELECT t.hashdiff
    FROM {{ this }} t
    WHERE t.hub_key = d.hub_key
      AND t.effective_from <= d.effective_from
    ORDER BY t.effective_from DESC, t.load_dts DESC
    LIMIT 1
) prior_version ON TRUE
LEFT JOIN {{ this }} exact_match
       ON exact_match.hub_key = d.hub_key
      AND exact_match.effective_from = d.effective_from
WHERE exact_match.hub_key IS NULL
  AND (prior_version.hashdiff IS NULL OR prior_version.hashdiff <> d.hashdiff)
{% endif %}
