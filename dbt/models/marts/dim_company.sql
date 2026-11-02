{{ config(order_by='company_key') }}

-- `v.` qualifiers keep the key expression on raw columns (ClickHouse aliases shadow columns).
select
    cityHash64(v.source, ifNull(v.company_id, ifNull(v.company, ''))) as company_key,
    v.source as source,
    any(v.company_id) as company_id,
    any(ifNull(v.company, 'Unknown')) as company_name,
    count() as vacancies
from {{ ref('int_vacancies_unified') }} as v
group by company_key, source
