"""Embeddings from Ollama's native /api/embed (batch input, one HTTP call per batch)."""

from collections.abc import Callable

import httpx

from jmi.config import settings

Embedder = Callable[[list[str]], list[list[float]]]

BATCH_SIZE = 32


class OllamaEmbedder:
    def __init__(self, model: str | None = None, base_url: str | None = None, client: httpx.Client | None = None):
        self.model = model or settings.embedding_model
        self.url = f"{base_url or settings.ollama_url}/api/embed"
        # First call loads the model into VRAM, which can take a while on a cold GPU.
        self.client = client or httpx.Client(timeout=300)

    def __call__(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), BATCH_SIZE):
            batch = texts[start:start + BATCH_SIZE]
            response = self.client.post(self.url, json={"model": self.model, "input": batch})
            response.raise_for_status()
            embeddings = response.json()["embeddings"]
            if len(embeddings) != len(batch):
                raise RuntimeError(f"Ollama returned {len(embeddings)} embeddings for {len(batch)} texts")
            vectors.extend(embeddings)
        return vectors
