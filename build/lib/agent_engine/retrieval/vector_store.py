"""Lightweight file-backed vector store with cosine similarity."""

from __future__ import annotations

import json
import logging
import math
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class StoredVector:
    vector_id: str
    values: List[float]
    metadata: Dict[str, Any]


class SimpleVectorStore:
    """JSON-backed vector store with cosine similarity search."""

    def __init__(self, path: str):
        self.path = path
        self.vectors: List[StoredVector] = []
        self._loaded = False

    def load(self) -> None:
        if self._loaded:
            return
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    raw = json.load(f) or []
                for entry in raw:
                    self.vectors.append(
                        StoredVector(
                            vector_id=entry.get("id") or entry.get("vector_id"),
                            values=entry.get("values") or entry.get("vector") or [],
                            metadata=entry.get("metadata") or {},
                        )
                    )
            except Exception as exc:
                logger.warning("Failed to load vector store %s: %s", self.path, exc)
        self._loaded = True

    def persist(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        data = [
            {"id": v.vector_id, "values": v.values, "metadata": v.metadata}
            for v in self.vectors
        ]
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def add(self, vector_id: str, values: List[float], metadata: Dict[str, Any]) -> None:
        self.load()
        self.vectors.append(StoredVector(vector_id=vector_id, values=values, metadata=metadata))

    def search(self, query: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        self.load()
        if not query:
            return []

        scored: List[tuple[float, StoredVector]] = []
        qnorm = _norm(query)
        if qnorm == 0:
            return []
        for vec in self.vectors:
            score = _cosine_similarity(query, vec.values, qnorm)
            scored.append((score, vec))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for score, vec in scored[:top_k]:
            results.append(
                {
                    "id": vec.vector_id,
                    "score": score,
                    "metadata": vec.metadata,
                }
            )
        return results


def _norm(vec: List[float]) -> float:
    return math.sqrt(sum(v * v for v in vec)) if vec else 0.0


def _cosine_similarity(a: List[float], b: List[float], norm_a: Optional[float] = None) -> float:
    if not a or not b:
        return 0.0
    norm_a = norm_a or _norm(a)
    norm_b = _norm(b)
    if norm_a == 0 or norm_b == 0 or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (norm_a * norm_b)
