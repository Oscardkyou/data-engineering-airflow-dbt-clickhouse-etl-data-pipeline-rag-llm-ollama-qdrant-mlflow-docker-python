{# Bring a salary amount to a monthly figure. 168 = 21 working days x 8 hours. #}
{% macro monthly_salary(amount, period) -%}
    multiIf(
        {{ period }} = 'month', {{ amount }},
        {{ period }} = 'year',  {{ amount }} / 12,
        {{ period }} = 'hour',  {{ amount }} * 168,
        NULL
    )
{%- endmacro %}
