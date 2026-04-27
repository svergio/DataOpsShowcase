{#
  Build a deterministic 64-char SHA-256 hashdiff from descriptive columns.
  Hashdiff is used for SCD2 change detection on satellites: if hashdiff differs
  between current row and incoming row, a new SCD2 version must be created.
  
  Notes:
  - NULLs are normalised to '^^' so column ordering changes do not silently break diffs.
  - String values are upper-cased for stability across casings.
#}
{% macro generate_hashdiff(columns) -%}
    {%- set ns = namespace(parts=[]) -%}
    {%- for col in columns -%}
        {%- set _ = ns.parts.append("COALESCE(NULLIF(TRIM(CAST(" ~ col ~ " AS TEXT)), ''), '^^')") -%}
    {%- endfor -%}
    ENCODE(
        DIGEST(
            UPPER(CONCAT_WS('||', {{ ns.parts | join(', ') }})),
            'sha256'
        ),
        'hex'
    )
{%- endmacro %}
