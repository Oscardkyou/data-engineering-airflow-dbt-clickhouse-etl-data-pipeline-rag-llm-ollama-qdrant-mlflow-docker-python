{{ config(severity='warn') }}

-- Salaries in a currency we have no rate for drop out of salary analytics. Warn, not fail:
-- a new exotic currency should not block the whole build, but we want to know.
select v.source, v.source_id, v.salary_currency
from {{ ref('int_vacancies_unified') }} as v
left join {{ ref('int_vacancy_salaries') }} as s
    on s.source = v.source and s.source_id = v.source_id
where v.salary_currency is not null
  and v.salary_period is not null
  and s.salary_month_usd_mid is null
settings join_use_nulls = 1
