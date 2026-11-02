{{ config(order_by='date_day') }}

-- Calendar covering every published date, so charts show days with zero new vacancies too.
with bounds as (
    select min(toDate(published_at)) as start_day, max(toDate(published_at)) as end_day
    from {{ ref('int_vacancies_unified') }}
)

select
    addDays(start_day, number) as date_day,
    toYear(date_day) as year,
    toMonth(date_day) as month,
    toISOWeek(date_day) as iso_week,
    toDayOfWeek(date_day) as day_of_week,
    day_of_week >= 6 as is_weekend
from bounds
array join range(toUInt32(dateDiff('day', start_day, end_day) + 1)) as number
