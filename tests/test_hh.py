from datetime import date

import httpx

from jmi.sources.hh import HHSource


def make_handler(load_fixture, requests: list[httpx.Request]):
    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/oauth/token":
            return httpx.Response(200, json={"access_token": "tkn", "token_type": "bearer"})
        if request.url.path == "/vacancies":
            assert request.headers["Authorization"] == "Bearer tkn"
            return httpx.Response(200, json=load_fixture("hh_search_page0.json"))
        vacancy_id = request.url.path.rsplit("/", 1)[-1]
        return httpx.Response(200, json=load_fixture(f"hh_vacancy_{vacancy_id}.json"))
    return handler


def make_source(handler, queries=("data engineer",)) -> HHSource:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return HHSource(list(queries), "id", "secret", "test-agent", client=client, sleep=lambda _: None)


def test_fetches_search_and_details_for_one_day(load_fixture):
    requests: list[httpx.Request] = []
    pages = list(make_source(make_handler(load_fixture, requests)).fetch(date(2026, 11, 1)))

    assert [p.key for p in pages] == [
        "search/data-engineer/page=000.json",
        "vacancy/120000001.json",
        "vacancy/120000002.json",
    ]
    assert pages[1].payload["key_skills"][0]["name"] == "Python"

    search = next(r for r in requests if r.url.path == "/vacancies")
    assert search.url.params["date_from"] == "2026-11-01"
    assert search.url.params["date_to"] == "2026-11-02"
    assert search.url.params["area"] == "40"


def test_vacancy_found_by_several_queries_is_fetched_once(load_fixture):
    requests: list[httpx.Request] = []
    pages = list(make_source(make_handler(load_fixture, requests), queries=("python", "data")).fetch(date(2026, 11, 1)))

    detail_keys = [p.key for p in pages if p.key.startswith("vacancy/")]
    assert detail_keys == ["vacancy/120000001.json", "vacancy/120000002.json"]
    assert len([p for p in pages if p.key.startswith("search/")]) == 2
