"""Stage 2: land raw API responses in s3://raw/{source}/dt=YYYY-MM-DD/.

Runs daily for the previous Almaty day. One task per source, so a failing source
does not block the others; each task updates its own Asset to trigger loading.
"""

import logging
from datetime import datetime, timedelta

import pendulum
from airflow.exceptions import AirflowSkipException
from airflow.sdk import dag, task
from airflow.timetables.interval import CronDataIntervalTimetable

from jmi.assets import CURRENCY_RATES, RAW
from jmi.sources.registry import SOURCE_NAMES

TZ = pendulum.timezone("Asia/Almaty")
log = logging.getLogger(__name__)

# A snapshot source run older than this is a backfill/catch-up, not "today".
SNAPSHOT_MAX_LAG = timedelta(hours=36)


def target_day(data_interval_start, data_interval_end):
    """(day to ingest, is_backfill).

    Scheduled runs cover [D-1, D) -> D-1. Airflow 3 manual runs have no data interval
    unless a logical date is given; treat them as "yesterday in Almaty", like the schedule.
    """
    if data_interval_start is None:
        end = pendulum.now(TZ).start_of("day")
        return end.subtract(days=1).date(), False
    is_backfill = pendulum.now("UTC") - data_interval_end > SNAPSHOT_MAX_LAG
    return data_interval_start.in_timezone(TZ).date(), is_backfill


@dag(
    # Data-interval timetable: the run at 00:00 on day D covers [D-1, D), so dt = D-1.
    schedule=CronDataIntervalTimetable("0 0 * * *", timezone=TZ),
    start_date=datetime(2026, 11, 1, tzinfo=TZ),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=5)},
    tags=["ingest"],
)
def ingest():
    for name in SOURCE_NAMES:

        @task(task_id=f"ingest_{name}", outlets=[RAW[name]])
        def ingest_source(source_name: str, data_interval_start=None, data_interval_end=None,
                          outlet_events=None) -> dict:
            from jmi.clients import s3_client
            from jmi.config import settings
            from jmi.sources.registry import build_source, is_enabled
            from jmi.storage import write_partition

            if not is_enabled(source_name):
                raise AirflowSkipException(f"{source_name} is disabled in .env")
            source = build_source(source_name)
            day, is_backfill = target_day(data_interval_start, data_interval_end)
            if source.snapshot and is_backfill:
                raise AirflowSkipException(f"{source_name} only has current jobs; cannot backfill {day}")

            stats = write_partition(s3_client(), settings.s3_bucket_raw, source_name, day, source.fetch(day))
            # The asset event tells the load DAG exactly which partition changed.
            outlet_events[RAW[source_name]].extra = {"source": source_name, "dt": stats["dt"]}
            return stats

        ingest_source(name)

    # Rates can land after the vacancies (provider outage, retries): dbt listens to this asset too.
    @task(outlets=[CURRENCY_RATES])
    def ingest_currency_rates(data_interval_start=None, data_interval_end=None) -> dict:
        """Reference data: small enough to land in S3 and ClickHouse in one step."""
        import json

        import httpx

        from jmi import currency, warehouse
        from jmi.clients import clickhouse_client, s3_client
        from jmi.config import settings
        from jmi.storage import partition_prefix

        day, is_backfill = target_day(data_interval_start, data_interval_end)
        with httpx.Client(headers={"User-Agent": settings.user_agent}, timeout=30) as client:
            frankfurter = hh = None
            try:
                frankfurter = currency.fetch_frankfurter(client, day)
            except httpx.HTTPError as exc:
                # One provider being down must not drop the other: hh still covers USD, EUR and KZT.
                log.warning("Frankfurter unavailable for %s: %s", day, exc)
            # hh only has today's rates: skip it on backfills, like snapshot job sources.
            if not is_backfill:
                hh = currency.fetch_hh(client)
        if frankfurter is None and hh is None:
            raise RuntimeError(f"no currency provider available for {day}")

        s3 = s3_client()
        for provider, body in (("frankfurter", frankfurter), ("hh", hh)):
            if body is not None:
                s3.put_object(Bucket=settings.s3_bucket_raw, Key=f"{partition_prefix('currency', day)}{provider}.json",
                              Body=json.dumps(body, ensure_ascii=False).encode("utf-8"))
        rows = currency.to_rows(day, frankfurter, hh)
        warehouse.replace_currency_rates(clickhouse_client(), day, rows)
        return {"dt": day.isoformat(), "rates": len(rows), "frankfurter": frankfurter is not None, "hh": hh is not None}

    ingest_currency_rates()


ingest()
