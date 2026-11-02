from datetime import date

from jmi.currency import to_rows

DAY = date(2026, 11, 2)  # a Monday after a weekend


def test_frankfurter_rows_keep_rate_date_and_add_usd_itself():
    body = {"base": "USD", "date": "2026-10-30", "rates": {"EUR": 0.9, "CAD": 1.4}}
    rows = to_rows(DAY, body, None)

    assert rows[0] == [DAY, "frankfurter", "USD", "USD", 1.0, date(2026, 10, 30)]
    assert {r[3] for r in rows} == {"USD", "EUR", "CAD"}
    assert all(r[5] == date(2026, 10, 30) for r in rows)  # ECB had no Friday->Monday update


def test_hh_rur_is_normalised_to_rub_and_zero_rates_dropped():
    hh = {"currency": [{"code": "RUR", "rate": 1.0}, {"code": "KZT", "rate": 5.63}, {"code": "XXX", "rate": 0}]}
    rows = to_rows(DAY, None, hh)

    assert [(r[1], r[2], r[3], r[4]) for r in rows] == [("hh", "RUB", "RUB", 1.0), ("hh", "RUB", "KZT", 5.63)]
