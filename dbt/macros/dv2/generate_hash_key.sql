{# 
  Build a deterministic 64-char SHA-256 hash key from a list of business-key columns.
  - Lower-cases and trims string values for stability.
  - Replaces NULL with the literal '^^' sentinel so missing components do not collapse different keys.
  - Output is a hex string of length 64.
  Usage: {{ generate_hash_key(['order_id', 'customer_id']) }}
#}
{% macro generate_hash_key(columns) -%}
    {%- set ns = namespace(parts=[]) -%}
    {%- for col in columns -%}
        {%- set _ = ns.parts.append("COALESCE(NULLIF(TRIM(CAST(" ~ col ~ " AS TEXT)), ''), '^^')") -%}
    {%- endfor -%}
    ENCODE(
        DIGEST(
            UPPER(
                CONCAT_WS('||', {{ ns.parts | join(', ') }})
            ),
            'sha256'
        ),
        'hex'
    )
{%- endmacro %}
