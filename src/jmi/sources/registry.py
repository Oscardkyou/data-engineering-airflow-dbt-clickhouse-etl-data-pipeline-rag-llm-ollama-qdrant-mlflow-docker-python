"""Build source adapters from settings. Adding a source = one adapter + one entry here."""

from jmi.config import Settings, settings
from jmi.sources.base import Source
from jmi.sources.hh import HHSource
from jmi.sources.himalayas import HimalayasSource

SOURCE_NAMES = ("hh", "himalayas")


def is_enabled(name: str, cfg: Settings = settings) -> bool:
    return {"hh": cfg.hh_enabled, "himalayas": cfg.himalayas_enabled}[name]


def build_source(name: str, cfg: Settings = settings) -> Source:
    if name == "hh":
        return HHSource(cfg.hh_queries, cfg.hh_client_id, cfg.hh_client_secret, cfg.user_agent)
    if name == "himalayas":
        return HimalayasSource(cfg.himalayas_queries, cfg.himalayas_max_pages, cfg.user_agent)
    raise ValueError(f"unknown source: {name}")
