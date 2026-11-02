{{ config(order_by='(date_day, source)') }}

-- New vacancies per published day and source, zero-filled from dim_date.
with sources as (
    select distinct source from {{ ref('fct_vacancy') }}
),

counts as (
    select published_date, source, count() as new_vacancies,
           countIf(salary_month_usd_mid is not null) as with_salary
    from {{ ref('fct_vacancy') }}
    group by published_date, source
)

select
    d.date_day as date_day,
    s.source as source,
    ifNull(c.new_vacancies, 0) as new_vacancies,
    ifNull(c.with_salary, 0) as with_salary
from {{ ref('dim_date') }} as d
cross join sources as s
left join counts as c on c.published_date = d.date_day and c.source = s.source
settings join_use_nulls = 1
