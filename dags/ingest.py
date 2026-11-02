"""Stage 2: land raw API responses in s3://raw/{source}/dt=YYYY-MM-DD/.

Runs daily for the previous Almaty day. One task per source, so a failing source
does not block the others; each task updates its own Asset to trigger loading.
"""

from datetime import datetime, timedelta

import pendulum
from airflow.exceptions import AirflowSkipException
from airflow.sdk import dag, task
from airflow.timetables.interval import CronDataIntervalTimetable

from jmi.assets import RAW
from jmi.sources.registry import SOURCE_NAMES

TZ = pendulum.timezone("Asia/Almaty")

# A snapshot source run older than this is a backfill/catch-up, not "today".
SNAPSHOT_MAX_LAG = timedelta(hours=36)


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
        def ingest_source(source_name: str, data_interval_start=None, data_interval_end=None) -> dict:
            from jmi.clients import s3_client
            from jmi.config import settings
            from jmi.sources.registry import build_source, is_enabled
            from jmi.storage import write_partition

            if not is_enabled(source_name):
                raise AirflowSkipException(f"{source_name} is disabled in .env")
            source = build_source(source_name)
            if source.snapshot and pendulum.now("UTC") - data_interval_end > SNAPSHOT_MAX_LAG:
                raise AirflowSkipException(
                    f"{source_name} only has current jobs; cannot backfill {data_interval_start}")

            day = data_interval_start.in_timezone(TZ).date()
            return write_partition(s3_client(), settings.s3_bucket_raw, source_name, day, source.fetch(day))

        ingest_source(name)


ingest()
