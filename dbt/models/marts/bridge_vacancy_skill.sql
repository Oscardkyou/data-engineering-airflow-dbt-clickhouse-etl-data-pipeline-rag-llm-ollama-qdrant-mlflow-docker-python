{{ config(order_by='(skill_key, vacancy_key)') }}

-- Many-to-many between vacancies and skills: a vacancy lists several skills.
select distinct
    cityHash64(source, source_id) as vacancy_key,
    cityHash64(skill) as skill_key
from {{ ref('int_vacancies_unified') }}
array join skills as skill
