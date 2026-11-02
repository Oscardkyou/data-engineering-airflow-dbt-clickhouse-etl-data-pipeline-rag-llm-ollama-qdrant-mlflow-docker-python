"""Airflow Assets shared between producer and consumer DAGs (data-aware scheduling)."""

from airflow.sdk import Asset

from jmi.sources.registry import SOURCE_NAMES

RAW = {name: Asset(f"s3://raw/{name}") for name in SOURCE_NAMES}
WAREHOUSE_VACANCIES = Asset("clickhouse://raw/vacancies")
MARTS = Asset("clickhouse://analytics/fct_vacancy")
