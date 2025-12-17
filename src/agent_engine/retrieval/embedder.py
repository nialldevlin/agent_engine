"""Embedding providers (pluggable) with default Ollama implementation."""

from __future__ import annotations

import logging
import os
import subprocess
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
        base_url: str | None = None,
        timeout: int = 30,
        transport=None,
        auto_pull: bool = True,
        auto_start: bool = True,
    ) -> None:
        self.model = model
        host = base_url or os.getenv("OLLAMA_HOST") or "http://localhost:11434"
        self.base_url = host.rstrip("/") + "/api/embeddings"
        self.tags_url = host.rstrip("/") + "/api/tags"
        self.pull_url = host.rstrip("/") + "/api/pull"
        self.timeout = timeout
        self.transport = transport or self._requests_transport
        self.auto_pull = auto_pull
        self.auto_start = auto_start

    def embed(self, texts: List[str]) -> List[List[float]]:
        embeddings: List[List[float]] = []
        # Ensure server/model readiness before embedding calls
        self._ensure_server_ready()
        self._ensure_model_available()
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

    def _ensure_server_ready(self) -> None:
        """Best-effort attempt to verify Ollama is reachable, optionally auto-start."""
        try:
            import requests
        except ImportError:
            return

        try:
            requests.get(self.tags_url, timeout=self.timeout).raise_for_status()
            return
        except Exception:
            if not self.auto_start:
                return
            try:
                subprocess.Popen(
                    ["ollama", "serve"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception as exc:
                logger.warning("Could not auto-start Ollama: %s", exc)
                return
            # No sleep; next request will retry

    def _ensure_model_available(self) -> None:
        if not self.auto_pull:
            return
        try:
            import requests
        except ImportError:
            return
        try:
            resp = requests.get(self.tags_url, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json() or {}
            models = {m.get("model") for m in data.get("models", []) if isinstance(m, dict)}
            if self.model in models:
                return
        except Exception:
            # Ignore and try pull
            pass
        try:
            pull_resp = requests.post(self.pull_url, json={"model": self.model}, timeout=self.timeout, stream=True)
            pull_resp.raise_for_status()
            for _ in pull_resp.iter_lines():
                pass
        except Exception as exc:
            logger.warning("Failed to auto-pull embedding model %s: %s", self.model, exc)


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
