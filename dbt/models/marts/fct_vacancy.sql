{{ config(order_by='(published_date, vacancy_key)') }}

-- Grain: one row per vacancy (latest version). Keys are deterministic hashes, so dimensions
-- and facts can be rebuilt independently and still join.
select
    cityHash64(v.source, v.source_id) as vacancy_key,
    cityHash64(v.source, ifNull(v.company_id, ifNull(v.company, ''))) as company_key,
    cityHash64(ifNull(v.city, ''), ifNull(v.country, ''), v.is_remote) as location_key,
    toDate(v.published_at) as published_date,
    v.source as source,
    v.source_id as source_id,
    v.title as title,
    v.url as url,
    v.seniority_level as seniority_level,
    v.employment_type as employment_type,
    v.is_remote as is_remote,
    v.first_seen_dt as first_seen_dt,
    v.last_seen_dt as last_seen_dt,
    dateDiff('day', v.first_seen_dt, v.last_seen_dt) + 1 as days_seen,
    length(v.skills) as skills_count,
    v.salary_currency as salary_currency,
    s.salary_month_usd_from as salary_month_usd_from,
    s.salary_month_usd_to as salary_month_usd_to,
    s.salary_month_usd_mid as salary_month_usd_mid,
    s.salary_month_kzt_mid as salary_month_kzt_mid
from {{ ref('int_vacancies_unified') }} as v
left join {{ ref('int_vacancy_salaries') }} as s
    on s.source = v.source and s.source_id = v.source_id
settings join_use_nulls = 1
