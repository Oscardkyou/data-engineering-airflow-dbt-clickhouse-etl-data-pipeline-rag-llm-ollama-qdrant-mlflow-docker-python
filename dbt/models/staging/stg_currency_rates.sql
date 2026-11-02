-- Normalise both providers to "USD per 1 unit of currency".
with hh_usd as (
    -- hh quotes everything per 1 RUB; the USD row lets us cross-convert to USD.
    select dt, units_per_base as usd_per_rub
    from {{ source('raw', 'currency_rates') }}
    where provider = 'hh' and currency = 'USD'
)

select
    r.dt as dt,
    r.provider as provider,
    r.currency as currency,
    if(r.provider = 'frankfurter',
       1 / r.units_per_base,             -- units per USD -> USD per unit
       h.usd_per_rub / r.units_per_base  -- (USD per RUB) / (units per RUB)
    ) as usd_per_unit
from {{ source('raw', 'currency_rates') }} as r
left join hh_usd as h on h.dt = r.dt
where r.units_per_base > 0
  and (r.provider = 'frankfurter' or h.usd_per_rub > 0)
