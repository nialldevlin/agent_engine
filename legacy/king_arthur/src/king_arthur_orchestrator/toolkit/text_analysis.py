"""Deterministic text analysis helpers shared across agents and tools."""

from __future__ import annotations

import re
from typing import Iterable, Sequence, Set

from king_arthur_orchestrator.toolkit.fuzzy import FuzzyMatch, fuzzy_match

STOP_WORDS: Set[str] = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "was", "are", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "should", "could", "can", "may", "might", "must", "i", "you",
    "he", "she", "it", "we", "they", "this", "that", "these", "those"
}


def extract_keywords(text: str, max_keywords: int = 20) -> Set[str]:
    """Extract keywords using lightweight heuristics."""
    keywords: Set[str] = set()
    if not text:
        return keywords

    words = re.findall(r"\w+", text.lower())
    for word in words:
        if word in STOP_WORDS or len(word) < 3:
            continue
        keywords.add(word)
        if len(keywords) >= max_keywords:
            break

    code_pattern = r"\b[a-zA-Z_][a-zA-Z0-9_]*\b"
    for term in re.findall(code_pattern, text):
        if "_" in term or (any(c.isupper() for c in term) and any(c.islower() for c in term)):
            keywords.add(term.lower())
            if len(keywords) >= max_keywords:
                break

    return keywords


def calculate_relevance_score(query_keywords: Set[str], doc_keywords: Set[str], doc_length: int) -> float:
    """BM25-inspired relevance score used by semantic memory/file context."""
    if not query_keywords or not doc_keywords:
        return 0.0

    overlap = query_keywords.intersection(doc_keywords)
    if not overlap:
        return 0.0

    match_ratio = len(overlap) / len(query_keywords)
    coverage = len(overlap) / len(doc_keywords) if doc_keywords else 0
    length_factor = 1.0 / (1.0 + abs(doc_length - 500) / 500.0)

    return match_ratio * 0.6 + coverage * 0.3 + length_factor * 0.1


def fuzzy_keywords(query: str, candidates: Sequence[str], recent: Iterable[str] | None = None, limit: int = 25) -> list[FuzzyMatch]:
    """Convenience wrapper that routes to the shared fuzzy matcher."""
    return fuzzy_match(query, candidates, recent=recent, limit=limit)


__all__ = [
    "STOP_WORDS",
    "extract_keywords",
    "calculate_relevance_score",
    "FuzzyMatch",
    "fuzzy_match",
    "fuzzy_keywords",
]
