import json
import pathlib

import pytest

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


@pytest.fixture
def load_fixture():
    def _load(name: str):
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return _load


class FakeS3:
    """In-memory stand-in for the few boto3 S3 calls the storage layer uses."""

    def __init__(self):
        self.objects: dict[tuple[str, str], bytes] = {}

    def put_object(self, Bucket, Key, Body, **_):  # noqa: N803 - boto3 argument names
        self.objects[(Bucket, Key)] = Body

    def delete_objects(self, Bucket, Delete):  # noqa: N803
        for obj in Delete["Objects"]:
            self.objects.pop((Bucket, obj["Key"]), None)

    def get_paginator(self, _name):
        store = self

        class Paginator:
            def paginate(self, Bucket, Prefix):  # noqa: N803
                keys = [k for b, k in store.objects if b == Bucket and k.startswith(Prefix)]
                yield {"Contents": [{"Key": k} for k in sorted(keys)]} if keys else {}

        return Paginator()

    def keys(self, bucket: str) -> list[str]:
        return sorted(k for b, k in self.objects if b == bucket)


@pytest.fixture
def fake_s3():
    return FakeS3()
