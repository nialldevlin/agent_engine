"""
Toolkit logging utilities for deterministic helpers and telemetry pipelines.

Provides safe append/rotation helpers plus empty-log cleanup hooks used across
conversation logging, CLI event logging, and telemetry ingestion.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from king_arthur_orchestrator.toolkit.base import ToolResult


def auto_cleanup_empty_log(
    path: Path,
    check_fn: Callable[[str], bool],
) -> bool:
    """
    Remove a log file when its contents match `check_fn` (e.g., empty or whitespace-only).
    """
    if not path.exists():
        return False

    try:
        content = path.read_text()
    except Exception:
        return False

    if check_fn(content):
        try:
            path.unlink()
        except Exception:
            return False
        return True

    return False


def safe_append_log(
    path: Path,
    content: str,
    encoding: str = "utf-8",
    ensure_trailing_newline: bool = True,
) -> ToolResult:
    """
    Append content to a log file with directory creation and error handling.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding=encoding) as handle:
            handle.write(content)
            if ensure_trailing_newline and not content.endswith("\n"):
                handle.write("\n")
        return ToolResult(True, output=f"Appended to log at {path}", metadata={"path": str(path)})
    except Exception as exc:
        return ToolResult(False, error=f"Failed to append to log {path}: {exc}")


def rotate_log_if_needed(
    path: Path,
    max_size: int,
    keep_count: int = 5,
) -> ToolResult:
    """
    Rotate the log file when it exceeds `max_size`, keeping at most `keep_count` archives.
    """
    if keep_count < 1:
        return ToolResult(False, error="keep_count must be >= 1")

    if not path.exists():
        return ToolResult(True, output="Log absent; nothing to rotate", metadata={"path": str(path)})

    try:
        if path.stat().st_size <= max_size:
            return ToolResult(True, output="Log size within threshold", metadata={"size": path.stat().st_size})
    except Exception as exc:
        return ToolResult(False, error=f"Failed to stat log {path}: {exc}")

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
        return ToolResult(False, error=f"Failed to rotate log {path}: {exc}")

    return ToolResult(
        True,
        output="Log rotated",
        metadata={"rotated_to": str(first_archive), "max_size": max_size, "keep_count": keep_count},
    )


__all__ = ["auto_cleanup_empty_log", "safe_append_log", "rotate_log_if_needed"]
