from datetime import UTC, date, datetime

from jmi.normalize import himalayas_id, iter_records, normalize_hh, normalize_himalayas
from jmi.schema import Vacancy, to_arrow

DAY = date(2026, 11, 1)


def test_hh_vacancy(load_fixture):
    rec = normalize_hh(load_fixture("hh_vacancy_120000001.json"), DAY)

    assert rec["source_id"] == "120000001"
    assert rec["city"] == "Алматы" and rec["country"] == "Kazakhstan"
    assert rec["is_remote"] is True
    assert (rec["salary_from"], rec["salary_to"], rec["salary_currency"], rec["salary_period"]) == (
        800000.0, 1200000.0, "KZT", "month")
    assert rec["published_at"] == datetime(2026, 11, 1, 5, 15, tzinfo=UTC)
    # key_skills merged with skills found in the description ("dbt" is only in the text)
    assert {"Python", "SQL", "Apache Airflow", "ClickHouse", "dbt", "ETL"} <= set(rec["skills"])
    Vacancy.model_validate(rec)


def test_hh_without_salary(load_fixture):
    rec = normalize_hh(load_fixture("hh_vacancy_120000002.json"), DAY)

    assert rec["salary_from"] is None and rec["salary_period"] is None
    assert rec["is_remote"] is False


def test_himalayas_job(load_fixture):
    job = load_fixture("himalayas_search.json")["jobs"][0]
    rec = normalize_himalayas(job, DAY)

    assert rec["source_id"] == "example-analytics/senior-data-engineer"
    assert rec["is_remote"] is True and rec["city"] == "remote"
    assert rec["location_restrictions"] == ["Kazakhstan", "Poland"]
    assert (rec["salary_from"], rec["salary_currency"], rec["salary_period"]) == (120000.0, "USD", "year")
    assert rec["seniority"] == "Senior"
    assert {"Apache Airflow", "dbt", "Snowflake", "Python", "SQL"} <= set(rec["skills"])


def test_himalayas_same_job_title_at_two_companies_gets_two_ids():
    a = himalayas_id("https://himalayas.app/companies/acme/jobs/senior-data-engineer")
    b = himalayas_id("https://himalayas.app/companies/globex/jobs/senior-data-engineer")

    assert a != b
    assert himalayas_id("https://example.com/odd") == "https://example.com/odd"  # unknown shape: keep guid


def test_himalayas_missing_salary_has_no_period(load_fixture):
    job = load_fixture("himalayas_search.json")["jobs"][1]
    rec = normalize_himalayas(job, DAY)

    assert rec["salary_from"] is None and rec["salary_currency"] is None and rec["salary_period"] is None


def test_hh_partition_uses_detail_pages_only(load_fixture):
    pages = {
        "search/python/page=000.json": load_fixture("hh_search_page0.json"),
        "vacancy/120000001.json": load_fixture("hh_vacancy_120000001.json"),
    }
    assert [r["source_id"] for r in iter_records("hh", pages, DAY)] == ["120000001"]


def test_records_convert_to_arrow(load_fixture):
    pages = {"search/x/page=001.json": load_fixture("himalayas_search.json")}
    table = to_arrow([Vacancy.model_validate(r) for r in iter_records("himalayas", pages, DAY)])

    assert table.num_rows == 2
    assert table.schema.field("published_at").type.tz == "UTC"
