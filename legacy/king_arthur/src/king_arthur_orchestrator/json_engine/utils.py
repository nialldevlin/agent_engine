"""
Robust, centralized JSON parsing module for LLM output handling.

Provides structured parsing with comprehensive error reporting, multiple
parsing strategies, and optional retry logic with re-prompting.

Key features:
- Fence-delimited JSON extraction (```json...```)
- Greedy regex fallback for naked JSON objects
- Multi-attempt parsing with different strategies
- Structured error results (not exceptions) with diagnostic info
- Optional retry logic with LLM re-prompting
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from json import JSONDecodeError
from typing import Any, Callable, Optional


# Configuration constants (remove magic numbers)
DEFAULT_MAX_BRACE_CANDIDATES = 25
DEFAULT_MAX_PARSE_ATTEMPTS = 3
DEFAULT_FENCE_EXTRACTION_TIMEOUT = 100


class ErrorClass(Enum):
    """Classification of JSON parsing errors by severity and repairability.

    - COSMETIC: Simple formatting issues (punctuation, fences, trailing commas)
    - STRUCTURAL: Mismatched or misplaced structural elements (braces, brackets, quotes)
    - FATAL: Non-recoverable errors (missing required fields, schema mismatch, non-JSON payload)
    """
    COSMETIC = "cosmetic"
    STRUCTURAL = "structural"
    FATAL = "fatal"


@dataclass
class ParseDiagnostics:
    """Diagnostic information about a parsing attempt or failure."""
    original_text: str
    original_length: int
    parse_attempts: list[dict] = field(default_factory=list)  # [{strategy, error, position_in_text}]
    last_error: Optional[str] = None
    attempted_strategies: list[str] = field(default_factory=list)

    def add_attempt(self, strategy: str, error: str, position: int = -1) -> None:
        """Record a parse attempt for diagnostics."""
        self.parse_attempts.append({
            "strategy": strategy,
            "error": error,
            "position": position
        })
        if strategy not in self.attempted_strategies:
            self.attempted_strategies.append(strategy)
        self.last_error = error


@dataclass
class ParseResult:
    """Result of a JSON parsing operation.

    Returns structured success/failure info instead of raising exceptions,
    allowing callers to handle failures gracefully.

    Attributes:
        success: Whether parsing succeeded.
        data: Parsed JSON object if successful, None otherwise.
        diagnostics: Detailed diagnostic info (original text, attempted strategies, errors).
        error_message: Human-readable error description if failed.
        error_class: Classification of the error (cosmetic, structural, fatal).
    """
    success: bool
    data: Optional[Any] = None
    diagnostics: Optional[ParseDiagnostics] = None
    error_message: Optional[str] = None
    error_class: Optional[ErrorClass] = None

    def __bool__(self) -> bool:
        """Allow ParseResult to be used in boolean contexts."""
        return self.success


def classify_json_error(
    error_message: str,
    content: str,
    diagnostics: Optional[ParseDiagnostics] = None
) -> ErrorClass:
    """
    Classify a JSON parsing error into cosmetic, structural, or fatal categories.

    Args:
        error_message: The error message from the parse attempt
        content: The original content that failed to parse
        diagnostics: Optional parse diagnostics with attempted strategies

    Returns:
        ErrorClass indicating the severity and repairability of the error

    Classification rules:
        - COSMETIC: Code fence wrappers, trailing commas, extra whitespace, simple quote issues
        - STRUCTURAL: Misplaced braces/brackets, unclosed structures, escaped quote issues
        - FATAL: Non-JSON payload, completely empty content, invalid data types
    """
    if not content or not isinstance(content, str):
        return ErrorClass.FATAL

    content_stripped = content.strip()
    error_lower = error_message.lower() if error_message else ""

    # FATAL: Empty or non-JSON content
    if not content_stripped:
        return ErrorClass.FATAL

    # FATAL: Content doesn't start with JSON structure at all
    starts_with_json = any(content_stripped.startswith(c) for c in ['{', '[', '"']) or \
                       content_stripped.startswith('```')

    if not starts_with_json:
        # Check if it looks like prose or non-JSON
        content_lower = content_stripped[:100].lower()
        fatal_indicators = [
            'error:', 'sorry', 'i cannot', 'i apologize', 'unable to',
            '<html', '<!doctype', 'http://', 'https://', 'i\'m sorry',
            'cannot', 'apologize'
        ]
        if any(indicator in content_lower for indicator in fatal_indicators):
            return ErrorClass.FATAL

        # If content doesn't start with JSON and has no braces/brackets, it's FATAL
        if '{' not in content_stripped and '[' not in content_stripped:
            return ErrorClass.FATAL

    # COSMETIC: Code fence issues (easily fixable)
    if '```' in content:
        return ErrorClass.COSMETIC

    # COSMETIC: Trailing comma (common LLM mistake, easily fixable)
    if 'trailing comma' in error_lower or ',]' in content or ',}' in content:
        return ErrorClass.COSMETIC

    # STRUCTURAL: Brace/bracket mismatch
    if any(indicator in error_lower for indicator in [
        'expecting', 'unterminated', 'unclosed', 'unexpected end',
        'mismatched', 'invalid escape'
    ]):
        # Count braces and brackets to determine if structural
        open_braces = content.count('{')
        close_braces = content.count('}')
        open_brackets = content.count('[')
        close_brackets = content.count(']')

        # Significant mismatch indicates structural problem
        if abs(open_braces - close_braces) > 1 or abs(open_brackets - close_brackets) > 1:
            return ErrorClass.STRUCTURAL

        # Minor mismatch might be cosmetic (single trailing issue)
        if abs(open_braces - close_braces) == 1 or abs(open_brackets - close_brackets) == 1:
            return ErrorClass.COSMETIC

    # STRUCTURAL: Quote issues (complex to repair)
    if 'quote' in error_lower or 'string' in error_lower:
        # Unescaped quotes in values are structural
        if 'unterminated string' in error_lower or 'invalid escape' in error_lower:
            return ErrorClass.STRUCTURAL
        # Simple quote issues might be cosmetic
        return ErrorClass.COSMETIC

    # STRUCTURAL: Control character issues
    if any(indicator in error_lower for indicator in ['control character', 'invalid character']):
        return ErrorClass.STRUCTURAL

    # FATAL: Invalid value types or schema issues
    if any(indicator in error_lower for indicator in [
        'invalid literal', 'invalid value', 'not valid json',
        'cannot deserialize', 'schema'
    ]):
        return ErrorClass.FATAL

    # Check if diagnostics show all strategies exhausted
    if diagnostics and len(diagnostics.attempted_strategies) >= 3:
        # If we tried multiple strategies and still failed, likely structural
        return ErrorClass.STRUCTURAL

    # Default to STRUCTURAL for unknown parsing issues
    return ErrorClass.STRUCTURAL


class JSONParser:
    """
    Centralized, robust JSON parser for LLM outputs.

    Implements multiple parsing strategies with fallbacks:
    1. Direct JSON parsing
    2. Fence-delimited extraction (```json...```)
    3. Greedy regex fallback for naked JSON objects
    4. Incremental raw_decode from brace positions

    Supports optional retry logic with LLM re-prompting for failed parses.
    """

    def __init__(
        self,
        max_brace_candidates: int = DEFAULT_MAX_BRACE_CANDIDATES,
        max_parse_attempts: int = DEFAULT_MAX_PARSE_ATTEMPTS,
    ):
        """
        Initialize the JSON parser.

        Args:
            max_brace_candidates: Maximum number of '{' positions to try raw_decode from.
            max_parse_attempts: Maximum number of parsing strategies to attempt.
        """
        self.max_brace_candidates = max_brace_candidates
        self.max_parse_attempts = max_parse_attempts
        self.decoder = json.JSONDecoder()

    def parse(self, content: str) -> ParseResult:
        """
        Parse JSON from LLM output content using multiple strategies.

        Attempts parsing in this order:
        1. Direct json.loads() on raw content
        2. Direct json.loads() after removing code fences
        3. Greedy regex extraction of JSON objects
        4. Incremental raw_decode from '{' positions

        Args:
            content: The text to parse (may contain code fences, extra text, etc.)

        Returns:
            ParseResult with success flag, parsed data, and diagnostics.
            Never raises exceptions; returns structured error results instead.
        """
        if not content or not isinstance(content, str):
            return ParseResult(
                success=False,
                error_message="Content must be a non-empty string",
                diagnostics=ParseDiagnostics(
                    original_text=str(content)[:100],
                    original_length=len(str(content)) if content else 0
                )
            )

        diagnostics = ParseDiagnostics(
            original_text=content[:500],  # Store first 500 chars for diagnostics
            original_length=len(content)
        )

        # Strategy 1: Direct parsing
        result = self._try_direct_parse(content, diagnostics)
        if result.success:
            return result

        # Strategy 2: Parse after fence removal
        stripped = self._strip_fences(content)
        if stripped != content:
            result = self._try_direct_parse(stripped, diagnostics, strategy="fence_removal")
            if result.success:
                return result

        # Strategy 3: Greedy regex extraction
        result = self._try_greedy_regex(content, diagnostics)
        if result.success:
            return result

        # Strategy 4: Incremental raw_decode from brace positions
        result = self._try_raw_decode_incremental(content, diagnostics)
        if result.success:
            return result

        # All strategies failed - classify the error
        error_msg = (
            f"Failed to parse JSON after {len(diagnostics.attempted_strategies)} strategies. "
            f"Attempted: {', '.join(diagnostics.attempted_strategies)}. "
            f"Last error: {diagnostics.last_error}. "
            f"Content preview: {content[:100]}..."
        )
        error_class = classify_json_error(
            error_message=diagnostics.last_error or "unknown",
            content=content,
            diagnostics=diagnostics
        )

        return ParseResult(
            success=False,
            diagnostics=diagnostics,
            error_message=error_msg,
            error_class=error_class
        )

    def parse_with_retry(
        self,
        content: str,
        retry_callback: Optional[Callable[[str], str]] = None,
        max_retries: int = 2,
    ) -> ParseResult:
        """
        Parse JSON with optional retry logic using LLM re-prompting.

        Args:
            content: Initial content to parse.
            retry_callback: Optional callable that takes error diagnostics and returns
                          a new content string to retry parsing. If None, no retries occur.
            max_retries: Maximum number of retry attempts (not counting initial attempt).

        Returns:
            ParseResult from successful parse or final failed attempt.
        """
        result = self.parse(content)
        if result.success or retry_callback is None:
            return result

        # Retry loop with re-prompting
        for attempt in range(max_retries):
            try:
                # Ask the callback to re-prompt the LLM for better output
                new_content = retry_callback(content)
                if new_content and new_content != content:
                    content = new_content
                    result = self.parse(content)
                    if result.success:
                        result.diagnostics.add_attempt(
                            f"retry_{attempt + 1}",
                            "success",
                            0
                        )
                        return result
                    else:
                        result.diagnostics.add_attempt(
                            f"retry_{attempt + 1}",
                            result.error_message or "parse failed",
                            0
                        )
            except Exception as e:
                result.diagnostics.add_attempt(
                    f"retry_{attempt + 1}",
                    f"retry_callback exception: {str(e)[:100]}",
                    0
                )

        return result

    def _try_direct_parse(
        self,
        content: str,
        diagnostics: ParseDiagnostics,
        strategy: str = "direct"
    ) -> ParseResult:
        """Try direct json.loads() on content."""
        try:
            data = json.loads(content)
            diagnostics.add_attempt(strategy, "success", 0)
            return ParseResult(
                success=True,
                data=data,
                diagnostics=diagnostics
            )
        except (json.JSONDecodeError, ValueError) as e:
            diagnostics.add_attempt(strategy, str(e)[:200], 0)
            return ParseResult(success=False, diagnostics=diagnostics)

    def _try_greedy_regex(
        self,
        content: str,
        diagnostics: ParseDiagnostics,
    ) -> ParseResult:
        """
        Try to extract JSON using greedy regex pattern.

        Looks for patterns like {...} or [...] and attempts to parse them.
        Uses incremental parsing to avoid overly-greedy matches.
        """
        strategy = "greedy_regex"

        # Look for potential JSON objects/arrays
        patterns = [
            (r'\{[^{}]*\}', 'object'),       # Simple objects
            (r'\[[^\[\]]*\]', 'array'),      # Simple arrays
            (r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', 'nested_object'),  # Nested objects
        ]

        for pattern, pattern_type in patterns:
            try:
                matches = re.finditer(pattern, content)
                for match in matches:
                    candidate = match.group(0)
                    try:
                        data = json.loads(candidate)
                        diagnostics.add_attempt(strategy, f"success ({pattern_type})", match.start())
                        return ParseResult(
                            success=True,
                            data=data,
                            diagnostics=diagnostics
                        )
                    except (json.JSONDecodeError, ValueError):
                        continue
            except Exception:
                continue

        diagnostics.add_attempt(strategy, "no valid regex matches found", 0)
        return ParseResult(success=False, diagnostics=diagnostics)

    def _try_raw_decode_incremental(
        self,
        content: str,
        diagnostics: ParseDiagnostics,
    ) -> ParseResult:
        """
        Try incremental raw_decode from positions of '{' characters.

        Uses json.JSONDecoder.raw_decode() starting from each '{' position
        up to max_brace_candidates, avoiding overly-greedy parsing.
        """
        strategy = "raw_decode_incremental"

        brace_positions = [m.start() for m in re.finditer(r'\{', content)]

        for idx, position in enumerate(brace_positions):
            if idx >= self.max_brace_candidates:
                break

            try:
                obj, _ = self.decoder.raw_decode(content[position:])
                diagnostics.add_attempt(
                    strategy,
                    f"success at position {position}",
                    position
                )
                return ParseResult(
                    success=True,
                    data=obj,
                    diagnostics=diagnostics
                )
            except JSONDecodeError as e:
                diagnostics.add_attempt(strategy, str(e)[:100], position)
                continue
            except Exception as e:
                diagnostics.add_attempt(strategy, f"unexpected error: {str(e)[:100]}", position)
                continue

        diagnostics.add_attempt(
            strategy,
            f"exhausted {len(brace_positions[:self.max_brace_candidates])} positions",
            0
        )
        return ParseResult(success=False, diagnostics=diagnostics)

    def _strip_fences(self, text: str) -> str:
        """
        Remove code fence delimiters (```...```) from text.

        Handles:
        - Opening fence with language specifier: ```json, ```python, etc.
        - Closing fence: ```
        """
        stripped = text.strip()

        # Remove opening fence with optional language specifier
        if stripped.startswith("```"):
            # Remove the opening ``` and any language specifier
            stripped = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", stripped, count=1).rstrip("`").strip()

        # Remove trailing closing fence
        if stripped.endswith("```"):
            stripped = stripped[:-3].strip()

        return stripped


# Global parser instance for backward compatibility
_default_parser = JSONParser()


def parse_json_safely(content: str, max_candidates: int = DEFAULT_MAX_BRACE_CANDIDATES) -> Any | None:
    """
    Legacy API for backward compatibility.

    Best-effort JSON parser:
    - Try direct loads
    - Try after removing code fences
    - Try raw_decode from the first few object delimiters

    Returns parsed object or None (not structured results).

    Args:
        content: Text to parse.
        max_candidates: Max number of brace positions to try.

    Returns:
        Parsed JSON object/array or None if parsing fails.
    """
    parser = JSONParser(max_brace_candidates=max_candidates)
    result = parser.parse(content)
    return result.data if result.success else None
