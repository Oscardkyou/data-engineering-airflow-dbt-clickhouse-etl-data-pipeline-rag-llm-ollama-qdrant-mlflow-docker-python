"""Settings read from environment variables (.env via docker compose)."""

import os
from dataclasses import dataclass, field


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def _flag(name: str, default: bool = False) -> bool:
    return _env(name, str(default)).lower() in {"1", "true", "yes"}


def _list(name: str, default: str) -> list[str]:
    return [item.strip() for item in _env(name, default).split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    s3_endpoint_url: str = field(default_factory=lambda: _env("S3_ENDPOINT_URL", "http://s3:8333"))
    s3_access_key: str = field(default_factory=lambda: _env("S3_ACCESS_KEY"))
    s3_secret_key: str = field(default_factory=lambda: _env("S3_SECRET_KEY"))
    s3_bucket_raw: str = field(default_factory=lambda: _env("S3_BUCKET_RAW", "raw"))
    s3_bucket_processed: str = field(default_factory=lambda: _env("S3_BUCKET_PROCESSED", "processed"))

    clickhouse_host: str = field(default_factory=lambda: _env("CLICKHOUSE_HOST", "clickhouse"))
    clickhouse_user: str = field(default_factory=lambda: _env("CLICKHOUSE_USER"))
    clickhouse_password: str = field(default_factory=lambda: _env("CLICKHOUSE_PASSWORD"))

    qdrant_url: str = field(default_factory=lambda: _env("QDRANT_URL", "http://qdrant:6333"))

    llm_base_url: str = field(default_factory=lambda: _env("LLM_BASE_URL", "http://host.docker.internal:11434/v1"))
    llm_model: str = field(default_factory=lambda: _env("LLM_MODEL", "qwen3:30b"))
    embedding_model: str = field(default_factory=lambda: _env("EMBEDDING_MODEL", "bge-m3"))

    user_agent: str = field(default_factory=lambda: _env("HTTP_USER_AGENT", "job-market-insights/0.1"))

    hh_enabled: bool = field(default_factory=lambda: _flag("HH_ENABLED"))
    hh_client_id: str = field(default_factory=lambda: _env("HH_CLIENT_ID"))
    hh_client_secret: str = field(default_factory=lambda: _env("HH_CLIENT_SECRET"))
    hh_queries: list[str] = field(
        default_factory=lambda: _list("HH_QUERIES", "data engineer,python,devops,machine learning"))

    himalayas_enabled: bool = field(default_factory=lambda: _flag("HIMALAYAS_ENABLED", True))
    himalayas_queries: list[str] = field(default_factory=lambda: _list(
        "HIMALAYAS_QUERIES", "data engineer,python developer,devops engineer,machine learning engineer"))
    himalayas_max_pages: int = field(default_factory=lambda: int(_env("HIMALAYAS_MAX_PAGES", "5")))

    @property
    def ollama_url(self) -> str:
        """Native Ollama API root (LLM_BASE_URL points at its OpenAI-compatible /v1)."""
        return self.llm_base_url.removesuffix("/").removesuffix("/v1")


settings = Settings()
