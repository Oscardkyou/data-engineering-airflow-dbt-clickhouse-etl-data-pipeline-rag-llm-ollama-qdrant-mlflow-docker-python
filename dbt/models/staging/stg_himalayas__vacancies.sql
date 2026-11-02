-- Himalayas: seniority is a comma-separated list ("Mid-level, Senior"); take the highest level.
select
    source,
    source_id,
    dt,
    title,
    company,
    company_id,
    url,
    published_at,
    city,
    country,
    is_remote,
    employment_type,
    multiIf(
        match(ifNull(seniority, ''), 'Director|Manager|Lead'), 'lead',
        position(ifNull(seniority, ''), 'Senior') > 0,          'senior',
        position(ifNull(seniority, ''), 'Mid') > 0,             'middle',
        position(ifNull(seniority, ''), 'Junior') > 0,          'junior',
        position(ifNull(seniority, ''), 'Entry') > 0,           'entry',
        'unknown'
    ) as seniority_level,
    salary_from,
    salary_to,
    salary_currency,
    salary_period,
    salary_gross,
    skills,
    categories,
    description_html,
    loaded_at
from {{ source('raw', 'vacancies') }}
where source = 'himalayas'
