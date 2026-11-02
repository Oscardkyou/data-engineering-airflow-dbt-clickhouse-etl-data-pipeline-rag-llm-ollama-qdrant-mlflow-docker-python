from datetime import date

import httpx

from jmi.sources.himalayas import HimalayasSource, slugify


def make_source(handler, queries=("data engineer",), max_pages=5) -> HimalayasSource:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return HimalayasSource(list(queries), max_pages, "test-agent", client=client, sleep=lambda _: None)


def full_page(n: int) -> dict:
    return {"jobs": [{"guid": f"job-{n}-{i}"} for i in range(20)]}


def test_stops_on_short_page(load_fixture):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["page"])
        calls.append(page)
        return httpx.Response(200, json=full_page(page) if page == 1 else load_fixture("himalayas_search.json"))

    pages = list(make_source(handler).fetch(date(2026, 11, 1)))

    assert calls == [1, 2]
    assert [p.key for p in pages] == ["search/data-engineer/page=001.json", "search/data-engineer/page=002.json"]
    assert "q=data+engineer" in pages[0].url


def test_respects_max_pages_and_empty_results():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params["q"] == "nothing":
            return httpx.Response(200, json={"jobs": []})
        return httpx.Response(200, json=full_page(int(request.url.params["page"])))

    pages = list(make_source(handler, queries=("python", "nothing"), max_pages=3).fetch(date(2026, 11, 1)))

    assert len(pages) == 3
    assert all(p.key.startswith("search/python/") for p in pages)


def test_payload_is_stored_untouched(load_fixture):
    body = load_fixture("himalayas_search.json")
    pages = list(make_source(lambda _: httpx.Response(200, json=body)).fetch(date(2026, 11, 1)))

    assert pages[0].payload == body


def test_slugify():
    assert slugify("Machine Learning / AI engineer") == "machine-learning-ai-engineer"
