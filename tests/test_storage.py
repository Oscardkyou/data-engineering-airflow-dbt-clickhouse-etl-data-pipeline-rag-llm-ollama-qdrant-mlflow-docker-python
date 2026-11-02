import json
from datetime import date

import pytest

from jmi.sources.base import RawPage
from jmi.storage import partition_prefix, write_partition

DAY = date(2026, 11, 1)


def pages(*keys: str) -> list[RawPage]:
    return [RawPage(key=k, payload={"key": k}, url=f"https://api.test/{k}") for k in keys]


def test_partition_layout():
    assert partition_prefix("hh", DAY) == "hh/dt=2026-11-01/"


def test_rerun_replaces_partition_without_stale_pages(fake_s3):
    write_partition(fake_s3, "raw", "hh", DAY, pages("a.json", "b.json", "c.json"))
    stats = write_partition(fake_s3, "raw", "hh", DAY, pages("a.json", "b.json"))

    assert fake_s3.keys("raw") == ["hh/dt=2026-11-01/a.json", "hh/dt=2026-11-01/b.json"]
    assert stats == {"source": "hh", "dt": "2026-11-01", "objects": 2, "replaced": 3}


def test_other_days_and_sources_are_untouched(fake_s3):
    write_partition(fake_s3, "raw", "hh", date(2026, 10, 31), pages("old.json"))
    write_partition(fake_s3, "raw", "himalayas", DAY, pages("x.json"))
    write_partition(fake_s3, "raw", "hh", DAY, pages("new.json"))

    assert fake_s3.keys("raw") == [
        "hh/dt=2026-10-31/old.json",
        "hh/dt=2026-11-01/new.json",
        "himalayas/dt=2026-11-01/x.json",
    ]


def test_failed_fetch_keeps_previous_data(fake_s3):
    write_partition(fake_s3, "raw", "hh", DAY, pages("a.json"))

    def broken():
        yield from pages("b.json")
        raise ConnectionError("API went down mid-run")

    with pytest.raises(ConnectionError):
        write_partition(fake_s3, "raw", "hh", DAY, broken())
    assert fake_s3.keys("raw") == ["hh/dt=2026-11-01/a.json"]


def test_payload_written_as_utf8_json(fake_s3):
    write_partition(fake_s3, "raw", "hh", DAY, [RawPage("v.json", {"name": "Дата-инженер"}, "u")])

    body = fake_s3.objects[("raw", "hh/dt=2026-11-01/v.json")]
    assert json.loads(body.decode("utf-8")) == {"name": "Дата-инженер"}
