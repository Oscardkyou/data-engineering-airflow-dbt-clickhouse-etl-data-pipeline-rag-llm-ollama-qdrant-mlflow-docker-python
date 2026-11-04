{{ config(order_by='(source, source_id)') }}

-- Monthly salary in USD and KZT. ASOF JOIN picks the latest rate on or before the day the
-- vacancy was observed, so weekends and missed currency runs still get a rate.
-- join_use_nulls: without it a missing rate becomes 0 (ClickHouse default) and the salary $0.
with salaried as (
    select
        source,
        source_id,
        dt,
        assumeNotNull(salary_currency) as currency,
        {{ monthly_salary('salary_from', 'salary_period') }} as month_from,
        {{ monthly_salary('salary_to', 'salary_period') }} as month_to
    from {{ ref('int_vacancies_unified') }}
    where salary_currency is not null
      and salary_period is not null
      and (salary_from is not null or salary_to is not null)
)

select
    s.source as source,
    s.source_id as source_id,
    s.currency as salary_currency,
    r.dt as rate_dt,
    s.month_from * r.usd_per_unit as salary_month_usd_from,
    s.month_to * r.usd_per_unit as salary_month_usd_to,
    -- midpoint of the range, or the single bound when only one is given
    coalesce((s.month_from + s.month_to) / 2, s.month_from, s.month_to) * r.usd_per_unit as salary_month_usd_mid,
    coalesce((s.month_from + s.month_to) / 2, s.month_from, s.month_to) * r.kzt_per_unit as salary_month_kzt_mid
from salaried as s
asof left join {{ ref('int_currency_rates_daily') }} as r
    on s.currency = r.currency and s.dt >= r.dt
settings join_use_nulls = 1
