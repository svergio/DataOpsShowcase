{# 
  Post-hook for SCD2 satellites: closes the previously-current row when a new version
  has been inserted with a different hashdiff. Operates on the model itself.

  Logic:
  - For each `hub_key`, find the row with `is_current = TRUE` and the next-newer row
    (ordered by `effective_from`). Set the older row's `effective_to` to the newer row's
    `effective_from` and `is_current = FALSE`.

  Works idempotently: re-running the post-hook only updates rows that need closing.
#}
{% macro end_date_current_records(hub_key_column='hub_key', timestamp_column='effective_from') -%}
WITH ranked AS (
    SELECT
        ctid,
        {{ hub_key_column }} AS hk,
        {{ timestamp_column }} AS eff_from,
        is_current,
        LEAD({{ timestamp_column }}) OVER (
            PARTITION BY {{ hub_key_column }}
            ORDER BY {{ timestamp_column }} ASC, hashdiff ASC
        ) AS next_eff_from
    FROM {{ this }}
)
UPDATE {{ this }} AS tgt
SET effective_to = ranked.next_eff_from,
    is_current = (ranked.next_eff_from IS NULL)
FROM ranked
WHERE tgt.ctid = ranked.ctid
  AND (
       tgt.effective_to IS DISTINCT FROM ranked.next_eff_from
    OR tgt.is_current   IS DISTINCT FROM (ranked.next_eff_from IS NULL)
  )
{%- endmacro %}
