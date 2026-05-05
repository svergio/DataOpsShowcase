{% macro dqc_fail_rows(from_relation, predicate_sql) %}
select *
from {{ from_relation }}
where ({{ predicate_sql }})
{% endmacro %}
