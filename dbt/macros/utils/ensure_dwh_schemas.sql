{# Ensure target schemas + required extensions exist before models run (idempotent). #}
{% macro ensure_dwh_schemas() %}
    {% set schemas = ['dwh_staging', 'dwh_vault', 'dwh_bdv', 'dwh_marts', 'dwh_serving', 'dwh_dq'] %}
    {% if execute %}
        {% do run_query("CREATE EXTENSION IF NOT EXISTS pgcrypto") %}
        {% for s in schemas %}
            {% do run_query("CREATE SCHEMA IF NOT EXISTS " ~ s) %}
        {% endfor %}
    {% endif %}
{% endmacro %}
