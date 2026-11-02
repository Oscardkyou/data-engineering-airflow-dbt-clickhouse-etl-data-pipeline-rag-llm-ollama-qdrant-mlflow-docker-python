from datetime import UTC, date, datetime

from jmi.quality import validate


def record(source_id: str, **overrides) -> dict:
    return {
        "source": "himalayas", "source_id": source_id, "dt": date(2026, 11, 1), "title": "Data Engineer",
        "url": f"https://example.com/{source_id}", "published_at": datetime(2026, 11, 1, tzinfo=UTC),
    } | overrides


def test_clean_batch_passes():
    vacancies, report = validate([record("a"), record("b")], history=[])

    assert report.ok and report.rows_valid == 2 and len(vacancies) == 2


def test_duplicates_are_collapsed_keeping_the_last():
    vacancies, report = validate([record("a", title="old"), record("a", title="new")], history=[])

    assert report.duplicates == 1
    assert [v.title for v in vacancies] == ["new"]


def test_few_invalid_rows_are_dropped_not_fatal():
    rows = [record(str(i)) for i in range(19)] + [record("bad", url="not-a-url")]
    vacancies, report = validate(rows, history=[])

    assert report.ok and report.invalid == 1 and len(vacancies) == 19
    assert report.samples and report.samples[0].startswith("bad:")


def test_many_invalid_rows_fail_the_load():
    rows = [record("ok")] + [record(f"bad{i}", title="") for i in range(3)]
    _, report = validate(rows, history=[])

    assert not report.ok and "failed validation" in report.errors[0]


def test_inverted_salary_range_is_invalid():
    _, report = validate([record("a", salary_from=5000, salary_to=1000)], history=[])

    assert report.invalid == 1


def test_empty_batch_fails():
    _, report = validate([], history=[])

    assert not report.ok and "empty" in report.errors[0]


def test_volume_anomaly_against_median():
    rows = [record(str(i)) for i in range(60)]

    _, normal = validate(rows, history=[100, 90, 110])           # 60% of median: fine
    _, too_few = validate(rows[:40], history=[100, 90, 110])     # 40%: anomaly

    assert normal.ok and normal.median_rows == 100
    assert not too_few.ok and "volume anomaly" in too_few.errors[0]


def test_no_anomaly_check_without_enough_history():
    _, report = validate([record("a")], history=[100, 100])

    assert report.ok and report.median_rows is None
