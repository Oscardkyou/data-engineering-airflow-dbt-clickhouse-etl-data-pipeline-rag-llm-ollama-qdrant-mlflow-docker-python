"""Factories for storage clients, so DAGs never build connections by hand."""

import boto3
import clickhouse_connect

from jmi.config import settings


def s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name="us-east-1",
    )


def clickhouse_client(database: str = "default"):
    return clickhouse_connect.get_client(
        host=settings.clickhouse_host,
        username=settings.clickhouse_user,
        password=settings.clickhouse_password,
        database=database,
    )
