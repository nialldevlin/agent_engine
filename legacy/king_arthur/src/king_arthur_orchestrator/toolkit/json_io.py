"""
Toolkit JSON helpers with safety wrappers for deterministic tools.

Provides shared helpers that centralize JSON read/write patterns, allow
structured validation, and report consistent error metadata.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from king_arthur_orchestrator.toolkit.base import ToolResult


JSONError = Optional[str]


def safe_read_json(
    path: Path,
    default: Any = None,
    encoding: str = "utf-8",
) -> Tuple[Any, JSONError]:
    """
    Read JSON content safely, returning the parsed value and an optional error.
    """
    try:
        payload = path.read_text(encoding=encoding)
    except FileNotFoundError:
        return default, f"JSON file not found: {path}"
    except Exception as exc:
        return default, f"Cannot read {path}: {exc}"

    try:
        return json.loads(payload), None
    except json.JSONDecodeError as exc:
        return default, f"Failed to parse JSON at {path}: {exc}"


def safe_write_json(
    path: Path,
    data: Any,
    indent: int = 2,
    ensure_ascii: bool = False,
    encoding: str = "utf-8",
) -> ToolResult:
    """
    Write JSON data with directory creation and structured ToolResult feedback.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(data, indent=indent, ensure_ascii=ensure_ascii)
        path.write_text(text + "\n", encoding=encoding)
        return ToolResult(True, output=f"Wrote JSON to {path}", metadata={"path": str(path)})
    except Exception as exc:
        return ToolResult(False, error=f"Failed to write JSON at {path}: {exc}")


def validate_json_structure(
    data: Any,
    required_keys: Iterable[str],
) -> Tuple[bool, List[str]]:
    """
    Ensure a JSON object contains the required keys, returning missing ones for logging.
    """
    if not isinstance(data, dict):
        return False, ["Data is not an object"]

    missing = [key for key in required_keys if key not in data]
    return not missing, missing


__all__ = ["safe_read_json", "safe_write_json", "validate_json_structure"]
