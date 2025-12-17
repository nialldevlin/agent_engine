"""Embedding providers (pluggable) with default Ollama implementation."""

from __future__ import annotations

import logging
from typing import List, Protocol

logger = logging.getLogger(__name__)


class EmbeddingProvider(Protocol):
    """Protocol for embedding providers."""

    def embed(self, texts: List[str]) -> List[List[float]]:
        ...


class OllamaEmbeddingProvider:
    """Local embeddings via Ollama."""

    def __init__(
        self,
        model: str = "nomic-embed-text",
        base_url: str = "http://localhost:11434/api/embeddings",
        timeout: int = 30,
        transport=None,
    ) -> None:
        self.model = model
        self.base_url = base_url
        self.timeout = timeout
        self.transport = transport or self._requests_transport

    def embed(self, texts: List[str]) -> List[List[float]]:
        embeddings: List[List[float]] = []
        for text in texts:
            try:
                resp = self.transport(
                    self.base_url,
                    {},
                    {
                        "model": self.model,
                        "prompt": text,
                    },
                )
                vec = _parse_embedding_response(resp)
                if vec is not None:
                    embeddings.append(vec)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Ollama embedding failed: %s", exc)
        return embeddings

    def _requests_transport(self, url: str, headers, payload):
        import requests

        r = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
        r.raise_for_status()
        return r


def _parse_embedding_response(resp) -> List[float] | None:
    if hasattr(resp, "json"):
        data = resp.json()
    else:
        data = resp
    if not data:
        return None
    # Ollama returns {"embedding": [...]} or {"data":[{"embedding":...}]}
    if isinstance(data, dict) and "embedding" in data:
        return data["embedding"]
    if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
        first = data["data"][0] if data["data"] else None
        if isinstance(first, dict) and "embedding" in first:
            return first["embedding"]
    return None
