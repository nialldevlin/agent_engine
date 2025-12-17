"""Retrieval orchestration: chunking, embedding, and search."""

from __future__ import annotations

import logging
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from .embedder import EmbeddingProvider
from .vector_store import SimpleVectorStore

logger = logging.getLogger(__name__)


@dataclass
class RetrievalDocument:
    doc_id: str
    text: str
    metadata: Dict[str, Any]


@dataclass
class RetrievalChunk:
    chunk_id: str
    text: str
    score: float
    metadata: Dict[str, Any]


class Retriever:
    """File-backed retrieval over workspace files and memory-like documents."""

    def __init__(
        self,
        workspace_root: str,
        embedder: EmbeddingProvider,
        store: SimpleVectorStore,
        chunk_size: int = 1200,
        chunk_overlap: int = 200,
        include_extensions: Optional[Sequence[str]] = None,
        max_file_kb: int = 512,
    ) -> None:
        self.workspace_root = workspace_root
        self.embedder = embedder
        self.store = store
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.include_extensions = set(include_extensions or [".py", ".md", ".txt", ".json", ".yaml", ".yml"])
        self.max_file_kb = max_file_kb
        self._indexed = False

    def index_workspace(self) -> None:
        """Index workspace files into the vector store (idempotent per process)."""
        if self._indexed:
            return
        documents = []
        for root, _, files in os.walk(self.workspace_root):
            for fname in files:
                if not self._is_allowed_file(fname):
                    continue
                fpath = os.path.join(root, fname)
                if os.path.getsize(fpath) > self.max_file_kb * 1024:
                    continue
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        text = f.read()
                except Exception:
                    continue
                documents.extend(self._chunk_text(text, fpath))

        if not documents:
            self._indexed = True
            return

        embeddings = self.embedder.embed([d.text for d in documents])
        for doc, emb in zip(documents, embeddings):
            self.store.add(doc.doc_id, emb, doc.metadata)
        self.store.persist()
        self._indexed = True

    def search(self, query: str, top_k: int = 5) -> List[RetrievalChunk]:
        """Search the vector store with a query string."""
        self.index_workspace()
        start = time.time()
        q_embeds = self.embedder.embed([query])
        if not q_embeds:
            return []
        results = self.store.search(q_embeds[0], top_k=top_k)
        latency_ms = int((time.time() - start) * 1000)
        chunks: List[RetrievalChunk] = []
        for res in results:
            chunks.append(
                RetrievalChunk(
                    chunk_id=res["id"],
                    text=res["metadata"].get("text", ""),
                    score=res["score"],
                    metadata={k: v for k, v in res["metadata"].items() if k != "text"},
                )
            )
        # Attach latency info on chunks metadata for downstream use
        for chunk in chunks:
            chunk.metadata.setdefault("retrieval_latency_ms", latency_ms)
        return chunks

    def _is_allowed_file(self, filename: str) -> bool:
        _, ext = os.path.splitext(filename)
        return ext.lower() in self.include_extensions

    def _chunk_text(self, text: str, path: str) -> List[RetrievalDocument]:
        """Chunk text by characters with overlap, including line references."""
        chunks: List[RetrievalDocument] = []
        lines = text.splitlines()
        current: List[str] = []
        start_line = 1
        i = 0
        while i < len(lines):
            current.append(lines[i])
            if sum(len(l) for l in current) >= self.chunk_size:
                end_line = i + 1
                chunk_text = "\n".join(current)
                chunks.append(
                    RetrievalDocument(
                        doc_id=f"{path}:{start_line}-{end_line}",
                        text=chunk_text,
                        metadata={
                            "path": path,
                            "start_line": start_line,
                            "end_line": end_line,
                            "text": chunk_text,
                        },
                    )
                )
                # overlap
                overlap_lines = self.chunk_overlap // max(len(current[0]) or 1, 1)
                current = current[-overlap_lines:] if overlap_lines > 0 else []
                start_line = end_line - len(current)
            i += 1

        if current:
            end_line = len(lines)
            chunk_text = "\n".join(current)
            chunks.append(
                RetrievalDocument(
                    doc_id=f"{path}:{start_line}-{end_line}",
                    text=chunk_text,
                    metadata={
                        "path": path,
                        "start_line": start_line,
                        "end_line": end_line,
                        "text": chunk_text,
                    },
                )
            )
        return chunks


def embed_memory_items(embedder: EmbeddingProvider, items: List[Dict[str, Any]], query: str, top_k: int = 3) -> List[RetrievalChunk]:
    """Compute relevance of memory items on the fly."""
    if not items:
        return []
    texts = [_stringify_payload(i) for i in items]
    q = embedder.embed([query])
    if not q:
        return []
    q_vec = q[0]
    item_vecs = embedder.embed(texts)
    results: List[RetrievalChunk] = []
    for item, vec in zip(items, item_vecs):
        score = _cosine(item_vec=vec, query_vec=q_vec)
        results.append(
            RetrievalChunk(
                chunk_id=item.get("context_item_id") or str(uuid.uuid4()),
                text=item.get("payload") if isinstance(item.get("payload"), str) else _stringify_payload(item),
                score=score,
                metadata={
                    "source": item.get("source", "memory"),
                    "kind": item.get("kind"),
                    "tags": item.get("tags", []),
                    "memory_id": item.get("context_item_id"),
                },
            )
        )
    results.sort(key=lambda c: c.score, reverse=True)
    return results[:top_k]


def _stringify_payload(item: Dict[str, Any]) -> str:
    payload = item.get("payload")
    if isinstance(payload, str):
        return payload
    return str(payload)


def _cosine(item_vec: List[float], query_vec: List[float]) -> float:
    import math

    if not item_vec or not query_vec or len(item_vec) != len(query_vec):
        return 0.0
    dot = sum(a * b for a, b in zip(item_vec, query_vec))
    norm_a = math.sqrt(sum(a * a for a in item_vec))
    norm_b = math.sqrt(sum(b * b for b in query_vec))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
