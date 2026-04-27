{#
  satellite_incremental — generic body for a SCD2 satellite model.

  Pipeline:
    1. Take source rows with hub_key, descriptive columns, load_dts, record_source.
    2. Deduplicate inside the batch by (hub_key, effective_from): keep the latest hashdiff.
    3. On first build (full refresh): emit one row per (hub_key, effective_from) directly.
       On incremental runs: compare each incoming row to the row that was active in the
       satellite at `effective_from`, append only when hashdiff differs.
    4. Inserted rows always carry is_current = TRUE / effective_to = NULL; the post-hook
       `scd2_recompute_timeline` then repairs the timeline (closes effective_to,
       collapses adjacent duplicates, fixes late-arriving overlaps).

  Args:
    source_relation : a CTE/ref returning at minimum:
                       hub_key, hashdiff, descriptive cols, effective_from, load_dts, record_source
    descriptive_cols: list of descriptive columns to project
#}
{% macro satellite_incremental(source_relation, descriptive_cols) -%}
WITH src_raw AS (
    SELECT
        hub_key,
        hashdiff,
        load_dts,
        effective_from,
        record_source
        {% for c in descriptive_cols %}, {{ c }}{% endfor %}
    FROM {{ source_relation }}
    WHERE hub_key IS NOT NULL
      AND hashdiff IS NOT NULL
      AND effective_from IS NOT NULL
),
src AS (
    SELECT *
    FROM (
        SELECT
            sr.*,
            ROW_NUMBER() OVER (
                PARTITION BY hub_key, effective_from
                ORDER BY load_dts DESC, hashdiff ASC
            ) AS rn
        FROM src_raw sr
    ) t
    WHERE rn = 1
)
SELECT
    src.hub_key,
    src.hashdiff,
    src.load_dts,
    src.effective_from,
    CAST(NULL AS TIMESTAMPTZ) AS effective_to,
    TRUE AS is_current,
    src.record_source
    {% for c in descriptive_cols %}, src.{{ c }}{% endfor %}
FROM src
{% if is_incremental() %}
LEFT JOIN LATERAL (
    SELECT t.hashdiff
    FROM {{ this }} t
    WHERE t.hub_key = src.hub_key
      AND t.effective_from <= src.effective_from
    ORDER BY t.effective_from DESC, t.load_dts DESC
    LIMIT 1
) AS prior_version ON TRUE
LEFT JOIN {{ this }} AS exact_match
       ON exact_match.hub_key = src.hub_key
      AND exact_match.effective_from = src.effective_from
WHERE exact_match.hub_key IS NULL
  AND (prior_version.hashdiff IS NULL OR prior_version.hashdiff <> src.hashdiff)
{% endif %}
{%- endmacro %}
