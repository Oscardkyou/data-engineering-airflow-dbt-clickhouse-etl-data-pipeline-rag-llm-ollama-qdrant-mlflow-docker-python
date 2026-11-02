{{ config(order_by='(currency, dt)') }}

-- One rate per currency and day. Frankfurter (ECB) wins where both providers quote a currency;
-- hh fills the gaps (KZT, UZS, ...). KZT per unit is derived through USD.
with ranked as (
    select
        dt,
        currency,
        usd_per_unit,
        row_number() over (partition by dt, currency order by provider = 'frankfurter' desc) as rn
    from {{ ref('stg_currency_rates') }}
),

daily as (
    select dt, currency, usd_per_unit from ranked where rn = 1
),

kzt as (
    select dt, usd_per_unit as usd_per_kzt from daily where currency = 'KZT'
)

select
    d.dt as dt,
    d.currency as currency,
    d.usd_per_unit as usd_per_unit,
    if(k.usd_per_kzt > 0, d.usd_per_unit / k.usd_per_kzt, NULL) as kzt_per_unit
from daily as d
left join kzt as k on k.dt = d.dt
