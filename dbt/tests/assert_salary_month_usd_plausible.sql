-- A monthly salary below $50 or above $100k almost always means a wrong period or currency
-- (e.g. an annual amount labelled monthly). Fails the build so it is fixed at the source.
select vacancy_key, source, source_id, salary_currency, salary_month_usd_mid
from {{ ref('fct_vacancy') }}
where salary_month_usd_mid is not null
  and (salary_month_usd_mid < 50 or salary_month_usd_mid > 100000)
