"""Connectivity checks for every external dependency of the pipeline."""

import httpx

from jmi.clients import clickhouse_client, s3_client
from jmi.config import settings


def check_s3() -> list[str]:
    return [b["Name"] for b in s3_client().list_buckets()["Buckets"]]


def check_clickhouse() -> list[str]:
    return [row[0] for row in clickhouse_client().query("SHOW DATABASES").result_rows]


def check_qdrant() -> str:
    return httpx.get(f"{settings.qdrant_url}/", timeout=10).raise_for_status().json()["version"]


def check_ollama() -> list[str]:
    """Return available model names; fail if the configured ones are missing."""
    tags = httpx.get(f"{settings.ollama_url}/api/tags", timeout=10).raise_for_status().json()
    models = [m["name"] for m in tags["models"]]
    missing = [
        name for name in (settings.llm_model, settings.embedding_model)
        if not any(m == name or m.startswith(f"{name}:") for m in models)
    ]
    if missing:
        raise RuntimeError(f"Ollama models not pulled: {missing}. Run: ollama pull <model>")
    return models
