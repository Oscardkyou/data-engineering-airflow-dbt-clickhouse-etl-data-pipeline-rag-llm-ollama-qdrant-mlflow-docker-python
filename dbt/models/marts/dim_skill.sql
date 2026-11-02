{{ config(order_by='skill_key') }}

select distinct
    cityHash64(skill) as skill_key,
    skill as skill_name
from {{ ref('int_vacancies_unified') }}
array join skills as skill
