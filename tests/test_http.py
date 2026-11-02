import httpx
import pytest

from jmi.http import get_json


def client_with(responses: list[httpx.Response]) -> httpx.Client:
    queue = iter(responses)
    return httpx.Client(transport=httpx.MockTransport(lambda request: next(queue)))


def test_retries_rate_limit_then_succeeds():
    sleeps = []
    client = client_with([httpx.Response(429), httpx.Response(503), httpx.Response(200, json={"ok": True})])

    assert get_json(client, "https://api.test/x", sleep=sleeps.append, backoff=1) == {"ok": True}
    assert sleeps == [1, 2]  # exponential backoff


def test_honours_retry_after_header():
    sleeps = []
    client = client_with([httpx.Response(429, headers={"Retry-After": "7"}), httpx.Response(200, json=[])])

    get_json(client, "https://api.test/x", sleep=sleeps.append)
    assert sleeps == [7.0]


def test_gives_up_after_retries():
    client = client_with([httpx.Response(429)] * 3)

    with pytest.raises(httpx.HTTPStatusError):
        get_json(client, "https://api.test/x", retries=2, sleep=lambda _: None)


def test_client_errors_are_not_retried():
    client = client_with([httpx.Response(403, json={"type": "forbidden"})])

    with pytest.raises(httpx.HTTPStatusError):
        get_json(client, "https://api.test/x", sleep=lambda _: pytest.fail("must not retry 403"))
