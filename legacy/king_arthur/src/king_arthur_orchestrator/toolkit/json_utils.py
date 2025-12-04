"""Toolkit entrypoints for JSON parsing utilities.

Centralizes deterministic JSON parsing, repair classification, and legacy
helpers so tools and orchestrator layers can import from the toolkit namespace
instead of reaching into ``json_engine.utils`` directly.
"""

from __future__ import annotations

from king_arthur_orchestrator.json_engine.utils import (
    DEFAULT_MAX_BRACE_CANDIDATES,
    DEFAULT_MAX_PARSE_ATTEMPTS,
    DEFAULT_FENCE_EXTRACTION_TIMEOUT,
    ErrorClass,
    JSONParser,
    ParseDiagnostics,
    ParseResult,
    classify_json_error,
    parse_json_safely,
)

__all__ = [
    "DEFAULT_MAX_BRACE_CANDIDATES",
    "DEFAULT_MAX_PARSE_ATTEMPTS",
    "DEFAULT_FENCE_EXTRACTION_TIMEOUT",
    "ErrorClass",
    "JSONParser",
    "ParseDiagnostics",
    "ParseResult",
    "classify_json_error",
    "parse_json_safely",
]
