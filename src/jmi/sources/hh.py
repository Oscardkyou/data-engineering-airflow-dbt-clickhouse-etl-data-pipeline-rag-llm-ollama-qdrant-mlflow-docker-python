"""hh.ru API (https://api.hh.ru). Since 2026 /vacancies requires an application token.

Search results lack the full description and key_skills, so for every vacancy found we
also fetch /vacancies/{id}. Unlike snapshot sources, hh supports date_from/date_to,
so past days can be backfilled (within hh's retention window).
"""

import time
from collections.abc import Iterator
from datetime import date, timedelta

import httpx

from jmi.http import get_json
from jmi.sources.base import RawPage

API = "https://api.hh.ru"
TOKEN_URL = "https://hh.ru/oauth/token"
PER_PAGE = 100
MAX_RESULTS = 2000  # hh never returns more than 2000 items per search, whatever the page
KAZAKHSTAN = 40


class HHSource:
    name = "hh"
    snapshot = False

    def __init__(self, queries: list[str], client_id: str, client_secret: str, user_agent: str,
                 area: int = KAZAKHSTAN, client: httpx.Client | None = None,
                 pause: float = 0.25, sleep=time.sleep):
        self.queries = queries
        self.client_id = client_id
        self.client_secret = client_secret
        self.area = area
        self.client = client or httpx.Client(headers={"HH-User-Agent": user_agent, "User-Agent": user_agent},
                                             timeout=30)
        self.pause = pause
        self.sleep = sleep

    def authenticate(self) -> None:
        resp = self.client.post(TOKEN_URL, data={
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        })
        resp.raise_for_status()
        self.client.headers["Authorization"] = f"Bearer {resp.json()['access_token']}"

    def fetch(self, day: date) -> Iterator[RawPage]:
        self.authenticate()
        seen: set[str] = set()
        for query in self.queries:
            for page in range(MAX_RESULTS // PER_PAGE):
                params = {
                    "text": query, "area": self.area, "per_page": PER_PAGE, "page": page,
                    # One calendar day per run keeps each search far below the 2000 cap.
                    "date_from": day.isoformat(), "date_to": (day + timedelta(days=1)).isoformat(),
                }
                body = get_json(self.client, f"{API}/vacancies", params=params, sleep=self.sleep)
                slug = query.lower().replace(" ", "-")
                yield RawPage(key=f"search/{slug}/page={page:03d}.json", payload=body,
                              url=str(httpx.URL(f"{API}/vacancies", params=params)))
                for item in body.get("items", []):
                    if item["id"] in seen:
                        continue  # the same vacancy matches several queries
                    seen.add(item["id"])
                    self.sleep(self.pause)
                    url = f"{API}/vacancies/{item['id']}"
                    yield RawPage(key=f"vacancy/{item['id']}.json",
                                  payload=get_json(self.client, url, sleep=self.sleep), url=url)
                if page + 1 >= body.get("pages", 0):
                    break
