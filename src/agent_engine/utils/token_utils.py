"""
Shared token estimation utilities.

Provides lightweight heuristics so CLI, toolkit tools, and memory managers use
the same approximations without duplicating logic.
"""

from __future__ import annotations

from typing import Any, Dict, List

CHARS_PER_TOKEN = 4


def estimate_tokens_rough(text: str) -> int:
    """Approximate token count using a simple chars-per-token heuristic."""
    if not text:
        return 0
    return max(1, len(text) // CHARS_PER_TOKEN)


def estimate_tokens_messages(messages: List[Dict[str, Any]]) -> int:
    """Estimate tokens for Claude-style message payloads."""
    total = 0
    for msg in messages or []:
        total += 5  # Role/metadata overhead
        for part in msg.get("content", []):
            if isinstance(part, dict):
                if part.get("type") == "text":
                    total += estimate_tokens_rough(part.get("text", ""))
                elif part.get("type") == "image":
                    total += 200  # Conservative default
            elif isinstance(part, str):
                total += estimate_tokens_rough(part)
    return total


def estimate_prompt_tokens(system: str, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]] | None = None) -> Dict[str, int]:
    """Estimate token usage for the full prompt payload."""
    return {
        "system": estimate_tokens_rough(system),
        "messages": estimate_tokens_messages(messages),
        "tools": len(tools or []) * 100,
    }


def estimate_tokens(text: str) -> int:
    """Alias kept for compatibility with the token budget manager."""
    return estimate_tokens_rough(text)


__all__ = [
    "estimate_tokens",
    "estimate_tokens_messages",
    "estimate_tokens_rough",
    "estimate_prompt_tokens",
]
