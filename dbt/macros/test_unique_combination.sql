{# Like dbt_utils.unique_combination_of_columns, without pulling a package at runtime. #}
{% test unique_combination(model, columns) %}
select {{ columns | join(', ') }}, count() as n
from {{ model }}
group by {{ columns | join(', ') }}
having n > 1
{% endtest %}
