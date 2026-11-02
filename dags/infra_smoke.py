"""Stage 1 smoke test: can Airflow tasks reach every service of the stack?

Trigger manually from the UI after `docker compose up`. All four tasks green = infra is ready.
"""

from datetime import datetime

from airflow.sdk import dag, task


@dag(schedule=None, start_date=datetime(2026, 1, 1), catchup=False, tags=["infra"])
def infra_smoke():
    @task
    def s3() -> list[str]:
        from jmi.healthcheck import check_s3
        return check_s3()

    @task
    def clickhouse() -> list[str]:
        from jmi.healthcheck import check_clickhouse
        return check_clickhouse()

    @task
    def qdrant() -> str:
        from jmi.healthcheck import check_qdrant
        return check_qdrant()

    @task
    def ollama() -> list[str]:
        from jmi.healthcheck import check_ollama
        return check_ollama()

    s3()
    clickhouse()
    qdrant()
    ollama()


infra_smoke()
