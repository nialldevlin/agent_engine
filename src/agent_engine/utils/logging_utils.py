"""Logging utilities for Agent Engine.

Provides safe append/rotation helpers plus empty-log cleanup hooks used across
conversation logging, CLI event logging, and telemetry ingestion.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Tuple, Optional, Dict, Any


def auto_cleanup_empty_log(
    path: Path,
    check_fn: Callable[[Path], bool],
) -> bool:
    """Remove a log file when check_fn returns True (e.g., when file is empty).

    Args:
        path: Path to the log file to check and potentially clean up.
        check_fn: Function that receives Path and returns True if file should be removed.

    Returns:
        True if file was cleaned up, False otherwise.
    """
    if not path.exists():
        return False

    try:
        # Call check_fn with the path object
        if check_fn(path):
            path.unlink()
            return True
    except Exception:
        return False

    return False


def safe_append_log(
    path: Path,
    content: str,
    encoding: str = "utf-8",
    ensure_trailing_newline: bool = True,
) -> Tuple[bool, Optional[str]]:
    """Append content to a log file with directory creation and error handling.

    Args:
        path: Path to the log file.
        content: Content to append to the log.
        encoding: Text encoding for the file (default: "utf-8").
        ensure_trailing_newline: If True, add newline if content doesn't end with one.

    Returns:
        Tuple of (success: bool, error_message: Optional[str]).
        If success is True, error_message is None.
        If success is False, error_message contains the error details.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding=encoding) as handle:
            handle.write(content)
            if ensure_trailing_newline and not content.endswith("\n"):
                handle.write("\n")
        return (True, None)
    except Exception as exc:
        return (False, f"Failed to append to log {path}: {exc}")


def rotate_log_if_needed(
    path: Path,
    max_size: int,
    keep_count: int = 3,
) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """Rotate the log file when it exceeds `max_size`, keeping at most `keep_count` archives.

    Archives are renamed with numeric suffixes (.1, .2, .3, etc.).
    Older archives are shifted up one slot and oldest are removed.

    Args:
        path: Path to the log file to rotate.
        max_size: Maximum file size in bytes before rotation.
        keep_count: Maximum number of archived log files to keep (default: 3).

    Returns:
        Tuple of (success: bool, error_message: Optional[str], metadata: Dict[str, Any]).
        Metadata contains rotation details like 'status', 'rotated_to', 'max_size', 'keep_count'.
    """
    metadata: Dict[str, Any] = {"path": str(path), "max_size": max_size, "keep_count": keep_count}

    if keep_count < 1:
        return (False, "keep_count must be >= 1", metadata)

    if not path.exists():
        metadata["status"] = "Log absent; nothing to rotate"
        return (True, None, metadata)

    try:
        current_size = path.stat().st_size
        if current_size <= max_size:
            metadata["size"] = current_size
            metadata["status"] = "Log size within threshold"
            return (True, None, metadata)
    except Exception as exc:
        return (False, f"Failed to stat log {path}: {exc}", metadata)

    # Shift older archives up one slot
    for slot in range(keep_count - 1, 0, -1):
        src = path.parent / f"{path.name}.{slot}"
        dst = path.parent / f"{path.name}.{slot + 1}"
        if src.exists():
            if dst.exists():
                dst.unlink()
            src.replace(dst)

    first_archive = path.parent / f"{path.name}.1"
    try:
        if first_archive.exists():
            first_archive.unlink()
        path.replace(first_archive)
    except Exception as exc:
        return (False, f"Failed to rotate log {path}: {exc}", metadata)

    metadata["rotated_to"] = str(first_archive)
    metadata["status"] = "Log rotated"
    return (True, None, metadata)


__all__ = ["auto_cleanup_empty_log", "safe_append_log", "rotate_log_if_needed"]
