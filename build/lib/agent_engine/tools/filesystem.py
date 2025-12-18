"""Filesystem tool handlers for Agent Engine.

These handlers are used by the ToolRuntime to perform safe reads/writes
within a configured workspace root. They rely on filesystem_safety
utilities to prevent traversal and enforce basic size limits.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Tuple

from agent_engine.utils.filesystem_safety import (
    DEFAULT_MAX_READ_BYTES,
    DEFAULT_MAX_WRITE_BYTES,
    is_binary_file,
    validate_path_traversal,
)


def _resolve_target(workspace_root: str | Path | None, target_path: str) -> Tuple[Path, Path]:
    root = Path(workspace_root or ".").expanduser().resolve()
    ok, err, resolved = validate_path_traversal(root, target_path)
    if not ok or resolved is None:
        raise ValueError(err or "Invalid path")
    return root, resolved


def write_file(inputs: Dict[str, Any], workspace_root: str | Path | None = None) -> Dict[str, Any]:
    """Write text content to a file within workspace_root."""
    target = inputs.get("path")
    content = inputs.get("content", "")
    max_bytes = int(inputs.get("max_bytes") or DEFAULT_MAX_WRITE_BYTES)

    if target is None:
        raise ValueError("Missing path for write_file")

    _, resolved = _resolve_target(workspace_root, target)
    data = content if isinstance(content, str) else str(content)
    encoded = data.encode("utf-8")
    if len(encoded) > max_bytes:
        raise ValueError(f"Content exceeds max_bytes ({max_bytes})")

    base_root = Path(workspace_root or ".").expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_bytes(encoded)

    return {
        "path": str(resolved),
        "relative_path": str(resolved.relative_to(base_root)),
        "bytes_written": len(encoded),
        "content": data,
    }


def read_file(inputs: Dict[str, Any], workspace_root: str | Path | None = None) -> Dict[str, Any]:
    """Read a text file within workspace_root with traversal and size limits."""
    target = inputs.get("path")
    max_bytes = int(inputs.get("max_bytes") or DEFAULT_MAX_READ_BYTES)

    if target is None:
        raise ValueError("Missing path for read_file")

    root, resolved = _resolve_target(workspace_root, target)
    if not resolved.exists():
        raise FileNotFoundError(f"File not found: {target}")

    if is_binary_file(resolved):
        raise ValueError(f"Refusing to read binary file: {target}")

    data = resolved.read_bytes()[:max_bytes]
    text = data.decode("utf-8", errors="replace")

    return {
        "path": str(resolved),
        "relative_path": str(resolved.relative_to(root)),
        "bytes_read": len(data),
        "content": text,
    }


def list_files(inputs: Dict[str, Any], workspace_root: str | Path | None = None) -> Dict[str, Any]:
    """List files within a directory under workspace_root."""
    target = inputs.get("path") or "."
    _, resolved = _resolve_target(workspace_root, target)
    if not resolved.exists():
        raise FileNotFoundError(f"Path not found: {target}")

    if resolved.is_file():
        entries = [str(resolved.name)]
    else:
        entries = sorted([p.name for p in resolved.iterdir()])

    return {
        "path": str(resolved),
        "entries": entries,
    }
