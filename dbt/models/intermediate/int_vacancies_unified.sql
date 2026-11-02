{{ config(order_by='(source, source_id)') }}

-- raw.vacancies holds one row per vacancy per day it was observed (snapshot sources repeat
-- open jobs daily). Keep the latest version and remember when the job was first/last seen.
with unioned as (
    select * from {{ ref('stg_hh__vacancies') }}
    union all
    select * from {{ ref('stg_himalayas__vacancies') }}
),

ranked as (
    select
        *,
        row_number() over (partition by source, source_id order by dt desc, loaded_at desc) as version_rank,
        min(dt) over (partition by source, source_id) as first_seen_dt,
        max(dt) over (partition by source, source_id) as last_seen_dt
    from unioned
)

select * except (version_rank)
from ranked
where version_rank = 1
