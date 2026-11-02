"""Stage 4: dbt models raw.vacancies into the analytics star schema.

`dbt build` runs models and their tests in DAG order, so a failing test stops everything
downstream of it instead of publishing marts built on bad data.
"""

from datetime import datetime

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import dag

from jmi.alerts import on_task_failure
from jmi.assets import MARTS, WAREHOUSE_VACANCIES

DBT = "/home/airflow/dbt-venv/bin/dbt"
DBT_ENV = {
    "DBT_PROFILES_DIR": "/opt/airflow/dbt",
    "DBT_PROJECT_DIR": "/opt/airflow/dbt",
    # Build artefacts stay inside the container, not in the (OneDrive-synced) repo.
    "DBT_TARGET_PATH": "/tmp/dbt/target",
    "DBT_LOG_PATH": "/tmp/dbt/logs",
}


@dag(
    schedule=[WAREHOUSE_VACANCIES],
    start_date=datetime(2026, 11, 1),
    catchup=False,
    max_active_runs=1,
    default_args={"on_failure_callback": on_task_failure},
    tags=["dbt"],
)
def dbt_transform():
    freshness = BashOperator(
        task_id="source_freshness",
        bash_command=f"{DBT} source freshness",
        env=DBT_ENV,
        append_env=True,
        # Stale sources are worth an alert but should not block rebuilding marts from what we have.
        on_failure_callback=None,
        trigger_rule="all_done",
    )
    build = BashOperator(
        task_id="dbt_build",
        bash_command=f"{DBT} build",
        env=DBT_ENV,
        append_env=True,
        outlets=[MARTS],
        trigger_rule="all_done",
    )
    freshness >> build


dbt_transform()
