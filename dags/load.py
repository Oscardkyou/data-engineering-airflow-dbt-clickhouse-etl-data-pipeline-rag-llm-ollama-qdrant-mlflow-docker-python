"""Stage 3: raw partitions -> quality gate -> Parquet -> ClickHouse raw.vacancies.

Triggered by ingest's Assets (no polling sensors): each asset event names the
source/day partition that changed. Manual runs can reload any partition via params.
"""

from datetime import datetime

from airflow.sdk import Param, dag, task

from jmi.assets import RAW, WAREHOUSE_VACANCIES

ANY_RAW = RAW["hh"] | RAW["himalayas"]


@dag(
    schedule=ANY_RAW,
    start_date=datetime(2026, 11, 1),
    catchup=False,
    max_active_runs=1,
    params={
        "source": Param(None, type=["null", "string"], enum=[None, *RAW], description="manual reload"),
        "dt": Param(None, type=["null", "string"], format="date", description="manual reload, YYYY-MM-DD"),
    },
    tags=["load"],
)
def load():
    @task
    def partitions_to_load(triggering_asset_events=None, params=None) -> list[dict]:
        if params.get("source") and params.get("dt"):
            return [{"source": params["source"], "dt": params["dt"]}]
        wanted = {
            (event.extra["source"], event.extra["dt"])
            for events in (triggering_asset_events or {}).values()
            for event in events
            if event.extra.get("source")
        }
        if not wanted:
            raise ValueError("nothing to load: trigger via ingest or pass source and dt params")
        return [{"source": s, "dt": d} for s, d in sorted(wanted)]

    # One mapped task instance per partition: a broken source does not block the others.
    @task(outlets=[WAREHOUSE_VACANCIES], max_active_tis_per_dag=2)
    def load_partition(partition: dict) -> dict:
        from datetime import date

        from jmi.clients import clickhouse_client, s3_client
        from jmi.config import settings
        from jmi.load import load_partition as run

        return run(s3_client(), clickhouse_client(), settings.s3_bucket_raw, settings.s3_bucket_processed,
                   partition["source"], date.fromisoformat(partition["dt"]))

    load_partition.expand(partition=partitions_to_load())


load()
