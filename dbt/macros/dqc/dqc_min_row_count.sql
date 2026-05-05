{% test dqc_min_row_count(model, min_count=1, where=none) %}
{% if where %}
with c as (select count(*) as n from {{ model }} where {{ where }})
{% else %}
with c as (select count(*) as n from {{ model }})
{% endif %}
select n from c where n < {{ min_count }}
{% endtest %}
