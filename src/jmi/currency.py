"""Daily currency rates for salary conversion.

Two free providers complement each other:
- Frankfurter (ECB): USD-based majors (EUR, CAD, PLN, INR, ...) for any past date, but no KZT;
- hh.ru /dictionaries: KZT, RUB, UZS, ... per 1 RUB, current snapshot only.
Rows are stored as "units of `currency` per 1 `base`"; dbt derives cross rates to USD/KZT.
"""

from datetime import date

import httpx

from jmi.http import get_json

FRANKFURTER_URL = "https://api.frankfurter.dev/v1/{day}"
HH_DICTIONARIES_URL = "https://api.hh.ru/dictionaries"


def fetch_frankfurter(client: httpx.Client, day: date) -> dict:
    # For weekends/holidays ECB returns the last business day; "date" in the body says which.
    return get_json(client, FRANKFURTER_URL.format(day=day.isoformat()), params={"base": "USD"})


def fetch_hh(client: httpx.Client) -> dict:
    return get_json(client, HH_DICTIONARIES_URL)


def to_rows(day: date, frankfurter: dict | None, hh: dict | None) -> list[list]:
    """[dt, provider, base, currency, units_per_base, rate_date] rows for raw.currency_rates."""
    rows = []
    if frankfurter:
        rate_date = date.fromisoformat(frankfurter["date"])
        rows.append([day, "frankfurter", "USD", "USD", 1.0, rate_date])
        rows += [[day, "frankfurter", "USD", cur, float(rate), rate_date]
                 for cur, rate in frankfurter["rates"].items()]
    if hh:
        # hh uses the legacy code RUR for the rouble; normalise to ISO 4217.
        rows += [[day, "hh", "RUB", "RUB" if c["code"] == "RUR" else c["code"], float(c["rate"]), day]
                 for c in hh.get("currency", []) if c.get("rate")]
    return rows
