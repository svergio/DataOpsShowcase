{% test dqc_non_negative_column(model, column_name, where=none) %}
select {{ column_name }}
from {{ model }}
where
  {% if where %}({{ where }}) and {% endif %}
  {{ column_name }} is not null
  and {{ column_name }} < 0
{% endtest %}
