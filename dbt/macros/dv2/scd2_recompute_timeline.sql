{#
  scd2_recompute_timeline — repairs SCD2 timelines after late-arriving inserts.

  Guarantees the following invariants per hub_key on `this`:
    * exactly one row has is_current = TRUE and it is the row with the maximum effective_from
    * effective_to[v_n] = effective_from[v_(n+1)] for consecutive versions
    * the most-recent row has effective_to = NULL
    * collapses adjacent duplicate hashdiffs to a single version (keeps earliest)

  Use this as the satellite post-hook instead of `end_date_current_records()` when the
  satellite must support late-arriving data and full timeline reconciliation.
#}
{% macro scd2_recompute_timeline(hub_key_column='hub_key') -%}
-- 1) Drop later duplicates that share the same hashdiff as the immediately preceding version.
WITH ordered AS (
    SELECT
        ctid,
        {{ hub_key_column }} AS hk,
        hashdiff,
        effective_from,
        LAG(hashdiff) OVER (
            PARTITION BY {{ hub_key_column }}
            ORDER BY effective_from ASC, load_dts ASC
        ) AS prev_hashdiff
    FROM {{ this }}
),
to_delete AS (
    SELECT ctid
    FROM ordered
    WHERE prev_hashdiff IS NOT NULL
      AND prev_hashdiff = hashdiff
)
DELETE FROM {{ this }} AS tgt
USING to_delete td
WHERE tgt.ctid = td.ctid;

-- 2) Recompute effective_to / is_current using window LEAD per hub_key.
WITH ranked AS (
    SELECT
        ctid,
        {{ hub_key_column }} AS hk,
        effective_from,
        LEAD(effective_from) OVER (
            PARTITION BY {{ hub_key_column }}
            ORDER BY effective_from ASC, load_dts ASC
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
