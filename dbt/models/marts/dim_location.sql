{{ config(order_by='location_key') }}

-- Columns are qualified with `v.` on purpose: in ClickHouse a SELECT alias is visible in the
-- whole query, so `ifNull(country, ...) AS country` would otherwise change the key's input.
select distinct
    cityHash64(ifNull(v.city, ''), ifNull(v.country, ''), v.is_remote) as location_key,
    ifNull(v.city, 'Unknown') as city,
    ifNull(v.country, 'Worldwide') as country,
    v.is_remote as is_remote
from {{ ref('int_vacancies_unified') }} as v
