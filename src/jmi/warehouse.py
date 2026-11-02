"""ClickHouse DDL and loading.

raw.vacancies is partitioned by (source, dt): reloading one source/day is an atomic
DROP PARTITION + INSERT, so reruns never duplicate rows and never touch other sources.
The same vacancy still appears once per day it was open; dbt picks the latest version.
"""

import json
from datetime import UTC, date, datetime

import pyarrow as pa

DDL = [
    """
    CREATE TABLE IF NOT EXISTS raw.vacancies
    (
        source                LowCardinality(String),
        source_id             String,
        dt                    Date,
        title                 String,
        company               Nullable(String),
        company_id            Nullable(String),
        url                   String,
        published_at          DateTime64(3, 'UTC'),
        city                  Nullable(String),
        country               Nullable(String),
        is_remote             Bool,
        location_restrictions Array(String),
        employment_type       Nullable(String),
        seniority             Nullable(String),
        salary_from           Nullable(Float64),
        salary_to             Nullable(Float64),
        salary_currency       Nullable(String),
        salary_period         Nullable(String),
        salary_gross          Nullable(Bool),
        skills                Array(String),
        categories            Array(String),
        description_html      String,
        loaded_at             DateTime64(3, 'UTC') DEFAULT now64(3)
    )
    ENGINE = MergeTree
    PARTITION BY (source, dt)
    ORDER BY (source, source_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS raw.load_audit
    (
        source     LowCardinality(String),
        dt         Date,
        status     LowCardinality(String),
        rows_raw   UInt32,
        rows_valid UInt32,
        invalid    UInt32,
        duplicates UInt32,
        report     String,
        loaded_at  DateTime64(3, 'UTC')
    )
    ENGINE = MergeTree
    ORDER BY (source, dt, loaded_at)
    """,
    """
    CREATE TABLE IF NOT EXISTS raw.currency_rates
    (
        dt             Date,
        provider       LowCardinality(String),
        base           LowCardinality(String),
        currency       LowCardinality(String),
        units_per_base Float64,
        rate_date      Date
    )
    ENGINE = MergeTree
    PARTITION BY toYYYYMM(dt)
    ORDER BY (dt, provider, currency)
    """,
]


def ensure_tables(ch) -> None:
    for statement in DDL:
        ch.command(statement)


def loaded_history(ch, source: str, before: date, days: int = 7) -> list[int]:
    """Rows loaded per day for the last `days` successful loads before `before`."""
    result = ch.query(
        """
        SELECT argMax(rows_valid, loaded_at)
        FROM raw.load_audit
        WHERE source = {source:String} AND dt < {before:Date} AND status = 'ok'
        GROUP BY dt ORDER BY dt DESC LIMIT {days:UInt32}
        """,
        parameters={"source": source, "before": before, "days": days},
    )
    return [row[0] for row in result.result_rows]


def replace_partition(ch, source: str, dt: date, table: pa.Table) -> None:
    ch.command(
        "ALTER TABLE raw.vacancies DROP PARTITION ({source:String}, {dt:Date})",
        parameters={"source": source, "dt": dt},
    )
    if table.num_rows:
        ch.insert_arrow("raw.vacancies", table)


def replace_currency_rates(ch, dt: date, rows: list[list]) -> None:
    """Idempotent per day: delete that day's rows, insert the fresh ones (tiny table, lightweight delete)."""
    ch.command("DELETE FROM raw.currency_rates WHERE dt = {dt:Date}", parameters={"dt": dt})
    if rows:
        ch.insert("raw.currency_rates", rows,
                  column_names=["dt", "provider", "base", "currency", "units_per_base", "rate_date"])


def write_audit(ch, source: str, dt: date, status: str, report: dict) -> None:
    ch.insert(
        "raw.load_audit",
        [[source, dt, status, report["rows_raw"], report["rows_valid"], report["invalid"],
          report["duplicates"], json.dumps(report, ensure_ascii=False), datetime.now(UTC)]],
        column_names=["source", "dt", "status", "rows_raw", "rows_valid", "invalid", "duplicates",
                      "report", "loaded_at"],
    )
