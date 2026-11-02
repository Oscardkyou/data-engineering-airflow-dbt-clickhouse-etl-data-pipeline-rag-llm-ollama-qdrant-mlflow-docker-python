{{ config(order_by='(currency, dt)') }}

select dt, currency, usd_per_unit, kzt_per_unit
from {{ ref('int_currency_rates_daily') }}
