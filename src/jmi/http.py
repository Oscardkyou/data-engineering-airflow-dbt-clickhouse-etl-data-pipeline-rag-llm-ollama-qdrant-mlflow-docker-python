"""HTTP helper with retry/backoff shared by all sources."""

import logging
import time

import httpx

log = logging.getLogger(__name__)

RETRY_STATUSES = {429, 500, 502, 503, 504}


def get_json(client: httpx.Client, url: str, *, params: dict | None = None, retries: int = 5,
             backoff: float = 2.0, sleep=time.sleep):
    """GET and decode JSON, retrying rate limits and server errors with exponential backoff.

    Honours Retry-After when the server sends it. `sleep` is injectable so tests run instantly.
    """
    for attempt in range(retries + 1):
        try:
            resp = client.get(url, params=params)
        except httpx.TransportError as exc:
            if attempt == retries:
                raise
            delay = backoff * 2**attempt
            log.warning("transport error %s on %s, retry in %.1fs", exc, url, delay)
            sleep(delay)
            continue
        if resp.status_code in RETRY_STATUSES and attempt < retries:
            retry_after = resp.headers.get("Retry-After")
            delay = float(retry_after) if retry_after and retry_after.isdigit() else backoff * 2**attempt
            log.warning("HTTP %s on %s, retry in %.1fs", resp.status_code, url, delay)
            sleep(delay)
            continue
        resp.raise_for_status()
        return resp.json()
    raise RuntimeError("unreachable")
