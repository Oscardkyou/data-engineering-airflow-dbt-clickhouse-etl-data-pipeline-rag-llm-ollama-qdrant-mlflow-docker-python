"""Stage 3 orchestration: raw JSON (S3) -> validated Parquet (S3) -> ClickHouse."""

import io
import json
import logging
from datetime import date

import pyarrow.parquet as pq

from jmi import warehouse
from jmi.normalize import iter_records
from jmi.quality import DataQualityError, validate
from jmi.schema import to_arrow
from jmi.storage import partition_prefix

log = logging.getLogger(__name__)


def read_raw_partition(s3, bucket: str, source: str, day: date) -> dict[str, object]:
    prefix = partition_prefix(source, day)
    pages = {}
    for listing in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
        for obj in listing.get("Contents", []):
            body = s3.get_object(Bucket=bucket, Key=obj["Key"])["Body"].read()
            pages[obj["Key"].removeprefix(prefix)] = json.loads(body)
    return pages


def load_partition(s3, ch, raw_bucket: str, processed_bucket: str, source: str, day: date) -> dict:
    pages = read_raw_partition(s3, raw_bucket, source, day)
    history = warehouse.loaded_history(ch, source, before=day)
    vacancies, report = validate(iter_records(source, pages, day), history)

    if not report.ok:
        warehouse.write_audit(ch, source, day, "failed", report.as_dict())
        raise DataQualityError(f"{source} {day}: {'; '.join(report.errors)}")

    table = to_arrow(vacancies)
    buffer = io.BytesIO()
    pq.write_table(table, buffer, compression="zstd")
    key = f"{partition_prefix(source, day)}vacancies.parquet"  # one deterministic file per partition
    s3.put_object(Bucket=processed_bucket, Key=key, Body=buffer.getvalue())

    warehouse.replace_partition(ch, source, day, table)
    warehouse.write_audit(ch, source, day, "ok", report.as_dict())
    log.info("%s %s: loaded %d rows, parquet s3://%s/%s", source, day, table.num_rows, processed_bucket, key)
    return {"source": source, "dt": day.isoformat(), **report.as_dict()}
