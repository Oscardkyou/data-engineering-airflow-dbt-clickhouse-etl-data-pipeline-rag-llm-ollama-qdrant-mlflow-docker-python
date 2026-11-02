"""Common contract for job sources.

A source only *fetches*: it yields API responses untouched. Normalisation to the
unified schema happens later (stage 3), so the raw layer can always be replayed.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol


@dataclass(frozen=True)
class RawPage:
    key: str          # path inside the source/day partition, e.g. "search/python/page=001.json"
    payload: Any      # response body exactly as the API returned it
    url: str          # request URL, kept as object metadata for lineage


class Source(Protocol):
    name: str
    # Snapshot sources only expose "jobs open right now", so a backfill for a past
    # day would silently store today's data under an old date. Those runs are skipped.
    snapshot: bool

    def fetch(self, day: date) -> Iterator[RawPage]: ...
