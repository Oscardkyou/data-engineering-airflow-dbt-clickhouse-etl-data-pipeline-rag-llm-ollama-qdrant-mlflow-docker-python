-- hh.ru: experience is a Russian label; map it to the shared seniority scale.
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
        seniority = 'Нет опыта',          'entry',
        seniority = 'От 1 года до 3 лет', 'junior',
        seniority = 'От 3 до 6 лет',      'middle',
        seniority = 'Более 6 лет',        'senior',
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
where source = 'hh'
