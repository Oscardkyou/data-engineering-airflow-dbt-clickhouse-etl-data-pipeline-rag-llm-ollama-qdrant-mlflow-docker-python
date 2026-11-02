{{ config(order_by='(seniority_level, skill_name)') }}

-- Which skills employers ask for, overall and by seniority. share = % of vacancies in the group.
with per_group as (
    select seniority_level, count() as group_vacancies
    from {{ ref('fct_vacancy') }}
    group by seniority_level
    union all
    select 'all', count() from {{ ref('fct_vacancy') }}
),

skill_counts as (
    select
        arrayJoin([f.seniority_level, 'all']) as seniority_level,
        s.skill_name as skill_name,
        count() as vacancies,
        countIf(f.salary_month_usd_mid is not null) as vacancies_with_salary,
        quantileExactIf(0.5)(f.salary_month_usd_mid, f.salary_month_usd_mid is not null) as median_salary_month_usd
    from {{ ref('fct_vacancy') }} as f
    inner join {{ ref('bridge_vacancy_skill') }} as b on b.vacancy_key = f.vacancy_key
    inner join {{ ref('dim_skill') }} as s on s.skill_key = b.skill_key
    group by seniority_level, skill_name
)

select
    c.seniority_level as seniority_level,
    c.skill_name as skill_name,
    c.vacancies as vacancies,
    round(100 * c.vacancies / g.group_vacancies, 1) as share_pct,
    c.vacancies_with_salary as vacancies_with_salary,
    -- a median over fewer than 5 salaries is noise; hide it rather than mislead
    if(c.vacancies_with_salary >= 5, round(c.median_salary_month_usd), NULL) as median_salary_month_usd
from skill_counts as c
inner join per_group as g on g.seniority_level = c.seniority_level
