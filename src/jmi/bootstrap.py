"""One-off setup run by the airflow-init container: create lake buckets.

Idempotent: safe to run on every `docker compose up`.
"""

import logging

from botocore.exceptions import ClientError

from jmi.clients import s3_client
from jmi.config import settings

log = logging.getLogger(__name__)

BUCKETS = (settings.s3_bucket_raw, settings.s3_bucket_processed, "mlflow")


def ensure_buckets() -> None:
    s3 = s3_client()
    for bucket in BUCKETS:
        try:
            s3.head_bucket(Bucket=bucket)
            log.info("bucket exists: %s", bucket)
        except ClientError:
            s3.create_bucket(Bucket=bucket)
            log.info("bucket created: %s", bucket)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ensure_buckets()
