{#
  hub_incremental — generic body for a Hub model.
  Produces an INSERT-only set of new hub rows: for every business key in the source
  that is not yet in the target, emit (hub_key, business_key, load_dts, record_source).

  Args:
    source_relation     : a relation/CTE/ref returning at least (business_key, load_dts, record_source)
    business_key_column : name of the BK column inside `source_relation` (default 'business_key')

  Note: must be used inside an `incremental` model materialisation.
#}
{% macro hub_incremental(source_relation, business_key_column='business_key') -%}
WITH src AS (
    SELECT
        {{ business_key_column }} AS business_key,
        load_dts,
        record_source
    FROM {{ source_relation }}
    WHERE {{ business_key_column }} IS NOT NULL
),
deduped AS (
    SELECT
        business_key,
        MIN(load_dts) AS load_dts,
        MIN(record_source) AS record_source
    FROM src
    GROUP BY business_key
)
SELECT
    {{ generate_hash_key(['business_key']) }} AS hub_key,
    business_key,
    load_dts,
    record_source
FROM deduped d
{% if is_incremental() %}
WHERE NOT EXISTS (
    SELECT 1
    FROM {{ this }} t
    WHERE t.business_key = d.business_key
)
{% endif %}
{%- endmacro %}
