"""JSON I/O utilities for Agent Engine.

Provides safe helpers for reading and writing JSON files with comprehensive
error handling, directory creation, and validation. These utilities centralize
JSON I/O patterns and provide consistent error reporting.

Design principles:
- Safe reads with fallback to defaults on error
- Safe writes with automatic directory creation
- Structured validation for JSON schema requirements
- Consistent error reporting as tuples (value, error_message)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, List, Optional, Tuple


def read_json_safe(
    path: Path,
    default: Any = None,
    encoding: str = "utf-8"
) -> Tuple[Any, Optional[str]]:
    """Read JSON content safely, returning data and optional error message.

    Attempts to read and parse a JSON file. On any error (file not found,
    read permission denied, JSON parse error), returns the default value
    and an error message describing what went wrong.

    Args:
        path: Path to the JSON file to read.
        default: Default value to return if reading or parsing fails. Defaults to None.
        encoding: Text encoding for file read. Defaults to "utf-8".

    Returns:
        Tuple of (data, error_message):
        - data: Parsed JSON value if successful, otherwise the default value.
        - error_message: None if successful, human-readable error string on failure.

    Examples:
        >>> data, err = read_json_safe(Path("config.json"), default={})
        >>> if err:
        ...     print(f"Failed to read config: {err}")
        ... else:
        ...     print(f"Config loaded: {data}")

        >>> data, err = read_json_safe(Path("missing.json"), default={"key": "value"})
        >>> print(data)  # {"key": "value"}
        >>> print(err)   # JSON file not found: ...
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


def write_json_safe(
    path: Path,
    data: Any,
    indent: int = 2,
    ensure_ascii: bool = False,
    encoding: str = "utf-8"
) -> Tuple[bool, Optional[str]]:
    """Write JSON data to file with directory creation and error handling.

    Automatically creates parent directories as needed. Adds a newline
    after JSON content for consistency. Returns success status and optional
    error message.

    Args:
        path: Path where JSON file should be written.
        data: Python object to serialize as JSON.
        indent: Number of spaces for JSON indentation. Defaults to 2.
        ensure_ascii: If True, non-ASCII characters are escaped. Defaults to False.
        encoding: Text encoding for file write. Defaults to "utf-8".

    Returns:
        Tuple of (success, error_message):
        - success: True if write completed successfully, False on error.
        - error_message: None if successful, human-readable error string on failure.

    Examples:
        >>> success, err = write_json_safe(Path("output.json"), {"key": "value"})
        >>> if success:
        ...     print("JSON written successfully")
        ... else:
        ...     print(f"Write failed: {err}")

        >>> # Creates nested directories automatically
        >>> success, err = write_json_safe(Path("deep/nested/config.json"), data)
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(data, indent=indent, ensure_ascii=ensure_ascii)
        path.write_text(text + "\n", encoding=encoding)
        return True, None
    except Exception as exc:
        return False, f"Failed to write JSON at {path}: {exc}"


def validate_json_structure(
    data: Any,
    required_keys: Iterable[str]
) -> Tuple[bool, List[str]]:
    """Validate that a JSON object contains all required keys.

    Checks that the provided data is a dictionary and contains all keys
    in the required_keys list. Returns a tuple with validation result
    and list of missing keys (if any).

    Args:
        data: Python object (typically from JSON parse) to validate.
        required_keys: Iterable of key names that must be present.

    Returns:
        Tuple of (is_valid, missing_keys):
        - is_valid: True if data is a dict with all required keys, False otherwise.
        - missing_keys: List of key names that are missing (empty if all present).
                        If data is not a dict, returns ["Data is not an object"].

    Examples:
        >>> data = {"name": "Alice", "age": 30}
        >>> is_valid, missing = validate_json_structure(data, ["name", "age"])
        >>> print(is_valid, missing)  # True, []

        >>> is_valid, missing = validate_json_structure(data, ["name", "email"])
        >>> print(is_valid, missing)  # False, ["email"]

        >>> is_valid, missing = validate_json_structure([1, 2, 3], ["key"])
        >>> print(is_valid, missing)  # False, ["Data is not an object"]
    """
    if not isinstance(data, dict):
        return False, ["Data is not an object"]

    missing = [key for key in required_keys if key not in data]
    return not missing, missing


__all__ = ["read_json_safe", "write_json_safe", "validate_json_structure"]
