{#
  scd2_merge — INSERT-only SCD2 detector for an `incremental` satellite model.

  Generates a SELECT statement that returns rows to be APPENDED to the satellite when:
    a) the hub_key is new (no row in the satellite at all), OR
    b) the latest row in the satellite for that hub_key has a different `hashdiff`
       than the incoming source row, OR
    c) the row arrives "late" — its `effective_from` falls between two existing
       versions and its hashdiff does not match the version active at that time.

  The companion macro `end_date_current_records` (or `scd2_recompute_timeline` for
  late-arriving repair) is run as a post-hook to close `effective_to` and `is_current`.

  Args:
    target_relation : the incremental satellite (this)
    source_relation : an alias/CTE/relation with the prepared incoming rows.
                      Must expose: hub_key, hashdiff, load_dts, effective_from, record_source,
                      and all descriptive columns.
    descriptive_cols: list of descriptive column names to project from `source_relation`.
#}
{% macro scd2_merge(target_relation, source_relation, descriptive_cols) -%}
WITH src AS (
    SELECT
        hub_key,
        hashdiff,
        load_dts,
        effective_from,
        record_source
        {% for c in descriptive_cols %}, {{ c }}{% endfor %}
    FROM {{ source_relation }}
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
LEFT JOIN {{ target_relation }} AS tgt
       ON tgt.hub_key = src.hub_key
      AND tgt.effective_from = src.effective_from
LEFT JOIN LATERAL (
    SELECT t.hashdiff
    FROM {{ target_relation }} t
    WHERE t.hub_key = src.hub_key
      AND t.effective_from <= src.effective_from
    ORDER BY t.effective_from DESC, t.load_dts DESC
    LIMIT 1
) AS prior_version ON TRUE
WHERE
    tgt.hub_key IS NULL
    AND (prior_version.hashdiff IS NULL OR prior_version.hashdiff <> src.hashdiff)
{%- endmacro %}
