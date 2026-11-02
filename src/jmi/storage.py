"""Raw layer of the data lake: s3://raw/{source}/dt=YYYY-MM-DD/{key}."""

import json
import logging
from collections.abc import Iterable
from datetime import UTC, date, datetime

from jmi.sources.base import RawPage

log = logging.getLogger(__name__)


def partition_prefix(source: str, day: date) -> str:
    return f"{source}/dt={day:%Y-%m-%d}/"


def write_partition(s3, bucket: str, source: str, day: date, pages: Iterable[RawPage]) -> dict:
    """Replace one source/day partition with freshly fetched pages.

    Idempotent: keys are deterministic and the partition is cleared first, so a rerun
    leaves exactly what the latest run fetched (no stale pages if a query got shorter).
    Pages are fetched before anything is deleted, so a failed fetch keeps the old data.
    """
    prefix = partition_prefix(source, day)
    pages = list(pages)
    deleted = delete_prefix(s3, bucket, prefix)
    fetched_at = datetime.now(UTC).isoformat()
    for page in pages:
        s3.put_object(
            Bucket=bucket,
            Key=prefix + page.key,
            Body=json.dumps(page.payload, ensure_ascii=False).encode("utf-8"),
            ContentType="application/json",
            Metadata={"source-url": page.url, "fetched-at": fetched_at},
        )
    log.info("%s: wrote %d objects to s3://%s/%s (replaced %d)", source, len(pages), bucket, prefix, deleted)
    return {"source": source, "dt": day.isoformat(), "objects": len(pages), "replaced": deleted}


def delete_prefix(s3, bucket: str, prefix: str) -> int:
    keys = [
        obj["Key"]
        for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix)
        for obj in page.get("Contents", [])
    ]
    for i in range(0, len(keys), 1000):  # S3 DeleteObjects accepts up to 1000 keys
        s3.delete_objects(Bucket=bucket, Delete={"Objects": [{"Key": k} for k in keys[i:i + 1000]]})
    return len(keys)
