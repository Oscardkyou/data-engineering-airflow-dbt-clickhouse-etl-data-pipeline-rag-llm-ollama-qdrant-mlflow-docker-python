"""Himalayas remote jobs API (https://himalayas.app/api): free, no key, attribution required.

The search endpoint returns 20 jobs per page and only the jobs open *now*, so this is a
snapshot source: we take the first N pages per query once a day and dedupe later in dbt.
"""

import re
import time
from collections.abc import Iterator
from datetime import date

import httpx

from jmi.http import get_json
from jmi.sources.base import RawPage

SEARCH_URL = "https://himalayas.app/jobs/api/search"
PAGE_SIZE = 20


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


class HimalayasSource:
    name = "himalayas"
    snapshot = True

    def __init__(self, queries: list[str], max_pages: int, user_agent: str,
                 client: httpx.Client | None = None, pause: float = 1.0, sleep=time.sleep):
        self.queries = queries
        self.max_pages = max_pages
        self.client = client or httpx.Client(headers={"User-Agent": user_agent}, timeout=30)
        self.pause = pause  # be polite: anonymous requests share one public rate limit
        self.sleep = sleep

    def fetch(self, day: date) -> Iterator[RawPage]:
        for query in self.queries:
            for page in range(1, self.max_pages + 1):
                params = {"q": query, "page": page}
                body = get_json(self.client, SEARCH_URL, params=params, sleep=self.sleep)
                jobs = body.get("jobs", [])
                if not jobs:
                    break
                yield RawPage(
                    key=f"search/{slugify(query)}/page={page:03d}.json",
                    payload=body,
                    url=str(httpx.URL(SEARCH_URL, params=params)),
                )
                if len(jobs) < PAGE_SIZE:
                    break  # last page
                self.sleep(self.pause)
