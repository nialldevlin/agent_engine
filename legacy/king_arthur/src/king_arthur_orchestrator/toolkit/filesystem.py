"""
Toolkit filesystem module: deterministic file I/O tools for agent consumption.

Provides a set of primitive file operation tools with comprehensive validation,
size limits, path traversal protection, binary file detection, and structured error
handling. Each tool declares its consent policy (NONE for read operations, REQUIRED
for destructive operations) and validates inputs before execution.

Design principles:
- Tools are deterministic and contain no LLM logic.
- All inputs are validated (path traversal, size limits, existence checks).
- Errors are returned as ToolResult, not raised as exceptions.
- Destructive operations (write, edit, delete) require explicit consent.
- Binary files are skipped with warnings rather than causing failures.
- Directory operations respect entry and depth limits.
- Configuration constants are explicit and easily adjustable.

File reference expansion (e.g., @file.txt syntax) is a separate orchestration layer
and is NOT handled by these primitive tools; see file_references.py for expansion.
"""

from __future__ import annotations

import difflib
import os
import stat
from pathlib import Path
from typing import Optional, Set, Tuple

from king_arthur_orchestrator.toolkit.base import Tool, ToolResult, ConsentPolicy, ConsentCategory

# Configuration constants for limits and validation
DEFAULT_MAX_READ_BYTES = 50_000  # Default max bytes for file_read
DEFAULT_MAX_WRITE_BYTES = 1_000_000  # Default max bytes for file_write
DEFAULT_MAX_GREP_RESULTS = 1000  # Max grep result lines
DEFAULT_MAX_LIST_ENTRIES = 500  # Max entries in directory listing
DEFAULT_MAX_DEPTH = 10  # Max recursion depth for directory operations

# Binary file extensions to skip (expanded from file_references.py)
SKIP_EXTENSIONS: Set[str] = {
    # Compiled/binary formats
    ".pyc", ".pyo", ".so", ".o", ".a", ".dll", ".exe", ".bin", ".out",
    # Images
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".ico", ".svg", ".webp", ".tiff",
    # Audio/Video
    ".mp3", ".mp4", ".avi", ".mov", ".wav", ".flac", ".mkv", ".m4a",
    # Archives
    ".zip", ".tar", ".gz", ".rar", ".7z", ".bz2", ".xz",
    # Documents
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    # Databases
    ".db", ".sqlite", ".sqlite3", ".mdb", ".accdb",
    # Node/Package managers
    ".node", ".whl",
    # Build artifacts
    ".o", ".obj", ".lib", ".dylib",
}


def _is_binary(path: Path) -> bool:
    """Check if file is likely binary based on extension or content sampling."""
    # Check extension
    if path.suffix.lower() in SKIP_EXTENSIONS:
        return True

    # Sample first 512 bytes to detect binary content
    try:
        with open(path, "rb") as f:
            chunk = f.read(512)
            if b"\x00" in chunk:
                return True
    except Exception:
        pass

    return False


def _validate_path_traversal(base_dir: Path, target: str) -> tuple[bool, str | None, Path | None]:
    """
    Validate that target path does not escape base_dir (path traversal attack prevention).

    Returns:
        (is_valid, error_message, resolved_path)
    """
    try:
        base = base_dir.resolve()
        candidate = (base / target).resolve()
        candidate.relative_to(base)  # Raises ValueError if outside base
        return True, None, candidate
    except ValueError:
        return False, f"Path traversal detected: {target} escapes workspace", None
    except Exception as e:
        return False, f"Invalid path: {str(e)}", None


def resolve_workspace_path(
    base_dir: Path,
    rel_path: str,
    validate: bool = True,
) -> ToolResult:
    """
    Ensure a relative path resolves inside the workspace and return the resolved path.
    """
    try:
        base = base_dir.resolve()
        candidate = (base / rel_path).resolve()
        if validate and not is_within_workspace(candidate, base):
            return ToolResult(False, error=f"{rel_path} escapes workspace {base}")
        return ToolResult(True, output=str(candidate), metadata={"resolved_path": str(candidate)})
    except Exception as exc:
        return ToolResult(False, error=f"Invalid path {rel_path}: {exc}")


def is_within_workspace(path: Path, workspace_root: Path) -> bool:
    """Return True if the path exists within the workspace root."""
    try:
        path.relative_to(workspace_root.resolve())
        return True
    except ValueError:
        return False


def normalize_workspace_path(path: str, workspace_root: Path) -> str:
    """Return the normalized relative path string (POSIX) inside the workspace."""
    resolved = (workspace_root / path).resolve()
    try:
        return resolved.relative_to(workspace_root.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def _file_read(base_dir: Path, path: str, max_bytes: int | None = None) -> ToolResult:
    """
    Read a file within the workspace.

    Args:
        base_dir: Base directory (workspace root).
        path: Relative file path.
        max_bytes: Maximum bytes to read (defaults to DEFAULT_MAX_READ_BYTES).

    Returns:
        ToolResult with file contents or error.
    """
    if max_bytes is None:
        max_bytes = DEFAULT_MAX_READ_BYTES

    # Validate path traversal
    is_valid, error, target = _validate_path_traversal(base_dir, path)
    if not is_valid:
        return ToolResult(False, error=error)

    # Check existence
    if not target.exists():
        return ToolResult(False, error=f"File does not exist: {path}")

    if not target.is_file():
        return ToolResult(False, error=f"Path is not a file: {path}")

    # Check if binary
    if _is_binary(target):
        return ToolResult(
            False,
            error=f"Binary or large file detected: {path}",
            metadata={"path": str(target), "size": target.stat().st_size}
        )

    # Check file size
    try:
        file_size = target.stat().st_size
        if file_size > max_bytes:
            return ToolResult(
                False,
                error=f"File too large: {file_size} bytes exceeds limit of {max_bytes}",
                metadata={"path": str(target), "size": file_size, "limit": max_bytes}
            )
    except Exception as e:
        return ToolResult(False, error=f"Cannot stat file: {str(e)}")

    # Read file
    try:
        data = target.read_text(errors="replace")
        return ToolResult(
            True,
            output=data,
            metadata={"path": str(target), "size": len(data)}
        )
    except Exception as e:
        return ToolResult(False, error=f"Cannot read file: {str(e)}")


def _file_write(base_dir: Path, path: str, content: str, max_bytes: int | None = None) -> ToolResult:
    """
    Write a file within the workspace (consent required).

    Creates parent directories as needed. If file exists, it is overwritten
    (no backup created by default; use file_edit for safer modifications).

    Args:
        base_dir: Base directory (workspace root).
        path: Relative file path.
        content: File contents to write.
        max_bytes: Maximum bytes to write (defaults to DEFAULT_MAX_WRITE_BYTES).

    Returns:
        ToolResult with status and path information.
    """
    if max_bytes is None:
        max_bytes = DEFAULT_MAX_WRITE_BYTES

    # Validate path traversal
    is_valid, error, target = _validate_path_traversal(base_dir, path)
    if not is_valid:
        return ToolResult(False, error=error)

    # Check content size
    if len(content) > max_bytes:
        return ToolResult(
            False,
            error=f"Content too large: {len(content)} bytes exceeds limit of {max_bytes}",
            metadata={"size": len(content), "limit": max_bytes}
        )

    # Write file
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, errors="replace")
        return ToolResult(
            True,
            output=f"Wrote {len(content)} bytes to {path}",
            metadata={"path": str(target), "size": len(content)}
        )
    except Exception as e:
        return ToolResult(False, error=f"Cannot write file: {str(e)}")


def _file_edit(base_dir: Path, path: str, old: str, new: str) -> ToolResult:
    """
    Edit a file by replacing the first occurrence of old with new (consent required).

    Uses anchor-based replacement (finds and replaces the first exact match of old).
    Generates and returns a unified diff showing the changes.

    Args:
        base_dir: Base directory (workspace root).
        path: Relative file path.
        old: Anchor text to find (must be an exact match).
        new: Replacement text.

    Returns:
        ToolResult with diff metadata and status.
    """
    # Validate path traversal
    is_valid, error, target = _validate_path_traversal(base_dir, path)
    if not is_valid:
        return ToolResult(False, error=error)

    # Check existence
    if not target.exists():
        return ToolResult(False, error=f"File does not exist: {path}")

    if not target.is_file():
        return ToolResult(False, error=f"Path is not a file: {path}")

    # Check if binary
    if _is_binary(target):
        return ToolResult(False, error=f"Binary file cannot be edited: {path}")

    # Read current content
    try:
        content = target.read_text(errors="replace")
    except Exception as e:
        return ToolResult(False, error=f"Cannot read file: {str(e)}")

    # Find anchor
    if old not in content:
        return ToolResult(
            False,
            error=f"Anchor text not found in file",
            metadata={"path": str(target), "anchor_length": len(old)}
        )

    # Perform replacement
    updated = content.replace(old, new, 1)

    # Generate diff
    try:
        diff_lines = list(difflib.unified_diff(
            content.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile=path,
            tofile=path,
            lineterm=""
        ))
        diff_output = "".join(diff_lines)
    except Exception:
        diff_output = "[Diff generation failed]"

    # Write updated content
    try:
        target.write_text(updated, errors="replace")
        return ToolResult(
            True,
            output="Edit successful",
            metadata={
                "path": str(target),
                "diff": diff_output,
                "old_length": len(old),
                "new_length": len(new)
            }
        )
    except Exception as e:
        return ToolResult(False, error=f"Cannot write file: {str(e)}")


def _file_delete(base_dir: Path, path: str) -> ToolResult:
    """
    Delete a file within the workspace (consent required).

    Args:
        base_dir: Base directory (workspace root).
        path: Relative file path.

    Returns:
        ToolResult with status.
    """
    # Validate path traversal
    is_valid, error, target = _validate_path_traversal(base_dir, path)
    if not is_valid:
        return ToolResult(False, error=error)

    # Check existence
    if not target.exists():
        return ToolResult(False, error=f"File does not exist: {path}")

    if not target.is_file():
        return ToolResult(False, error=f"Path is not a file: {path}")

    # Delete file
    try:
        target.unlink()
        return ToolResult(True, output=f"Deleted {path}", metadata={"path": str(target)})
    except Exception as e:
        return ToolResult(False, error=f"Cannot delete file: {str(e)}")


def _file_list(base_dir: Path, pattern: str = "*", max_entries: int | None = None) -> ToolResult:
    """
    List files matching a glob pattern within the workspace.

    Respects depth limits to prevent expensive recursive scans.
    Truncates results if they exceed max_entries.

    Args:
        base_dir: Base directory (workspace root).
        pattern: Glob pattern (e.g., "*.py", "src/**/*.ts").
        max_entries: Maximum entries to return (defaults to DEFAULT_MAX_LIST_ENTRIES).

    Returns:
        ToolResult with file listing.
    """
    if max_entries is None:
        max_entries = DEFAULT_MAX_LIST_ENTRIES

    try:
        # Use rglob for ** patterns, glob otherwise
        if "**" in pattern:
            matches = list(base_dir.rglob(pattern.replace("**/", "")))
        else:
            matches = list(base_dir.glob(pattern))

        # Sort and truncate
        matches = sorted(matches)[:max_entries]

        # Format output
        output_lines = [str(p.relative_to(base_dir)) for p in matches]
        output = "\n".join(output_lines)

        # Add truncation warning if needed
        if len(matches) >= max_entries:
            output += f"\n[Truncated to {max_entries} entries]"

        return ToolResult(
            True,
            output=output,
            metadata={"pattern": pattern, "count": len(output_lines), "truncated": len(matches) >= max_entries}
        )
    except Exception as e:
        return ToolResult(False, error=f"Cannot list files: {str(e)}")


def _file_grep(base_dir: Path, pattern: str, file_pattern: str = "**/*", max_results: int | None = None) -> ToolResult:
    """
    Search for a text pattern in files within the workspace.

    Performs simple substring matching (not regex). Skips binary files.
    Results are truncated to max_results lines.

    Args:
        base_dir: Base directory (workspace root).
        pattern: Substring to search for.
        file_pattern: Glob pattern for files to search (default "**/*").
        max_results: Maximum result lines to return (defaults to DEFAULT_MAX_GREP_RESULTS).

    Returns:
        ToolResult with matching lines.
    """
    if max_results is None:
        max_results = DEFAULT_MAX_GREP_RESULTS

    results = []
    try:
        # Resolve files matching pattern
        if "**" in file_pattern:
            file_root = base_dir
            glob_pattern = file_pattern.replace("**/", "")
            files = base_dir.rglob(glob_pattern) if glob_pattern else base_dir.rglob("*")
        else:
            files = base_dir.glob(file_pattern)

        for file_path in files:
            if not file_path.is_file():
                continue

            # Skip binary files
            if _is_binary(file_path):
                continue

            # Search in file
            try:
                with open(file_path, "r", errors="replace") as f:
                    for line_num, line in enumerate(f, 1):
                        if pattern in line:
                            rel_path = file_path.relative_to(base_dir)
                            results.append(f"{rel_path}:{line_num}:{line.rstrip()}")
                            if len(results) >= max_results:
                                break
            except Exception:
                continue

            if len(results) >= max_results:
                break

        output = "\n".join(results)
        if len(results) >= max_results:
            output += f"\n[Truncated to {max_results} results]"

        return ToolResult(
            True,
            output=output,
            metadata={"pattern": pattern, "file_pattern": file_pattern, "count": len(results), "truncated": len(results) >= max_results}
        )
    except Exception as e:
        return ToolResult(False, error=f"Cannot search files: {str(e)}")


def _file_info(base_dir: Path, path: str) -> ToolResult:
    """
    Get metadata about a file or directory.

    Returns file size, type, permissions, and modification time.
    Does not read file contents.

    Args:
        base_dir: Base directory (workspace root).
        path: Relative file path.

    Returns:
        ToolResult with file metadata.
    """
    # Validate path traversal
    is_valid, error, target = _validate_path_traversal(base_dir, path)
    if not is_valid:
        return ToolResult(False, error=error)

    # Check existence
    if not target.exists():
        return ToolResult(False, error=f"Path does not exist: {path}")

    # Collect metadata
    try:
        stat_info = target.stat()
        is_file = target.is_file()
        is_dir = target.is_dir()
        is_binary = _is_binary(target) if is_file else False

        metadata = {
            "path": str(target),
            "relative_path": path,
            "is_file": is_file,
            "is_directory": is_dir,
            "size": stat_info.st_size,
            "mode": oct(stat_info.st_mode),
            "modified": stat_info.st_mtime,
            "is_binary": is_binary,
        }

        if is_dir:
            # Count directory entries
            try:
                entries = list(target.iterdir())
                metadata["entry_count"] = len(entries)
            except Exception:
                metadata["entry_count"] = None

        output = f"Path: {path}\n"
        output += f"Type: {'File' if is_file else 'Directory' if is_dir else 'Other'}\n"
        output += f"Size: {stat_info.st_size} bytes\n"
        if is_binary and is_file:
            output += f"Binary: Yes\n"

        return ToolResult(True, output=output, metadata=metadata)
    except Exception as e:
        return ToolResult(False, error=f"Cannot stat path: {str(e)}")


def register_filesystem_tools(registry, base_dir: Path) -> None:
    """
    Register all filesystem tools with the given registry.

    Args:
        registry: Tool registry instance.
        base_dir: Base directory for all file operations (workspace root).
    """
    registry.register(Tool(
        name="file_read",
        description="Read a file within the workspace. Returns file contents. Skips binary files and enforces size limits.",
        execute=lambda path, max_bytes=None: _file_read(base_dir, path, max_bytes),
        parameters={
            "path": "Relative file path (string)",
            "max_bytes": "Maximum bytes to read (optional, default 50KB)"
        },
        consent=ConsentPolicy.NONE,
        side_effects=False,
    ))

    registry.register(Tool(
        name="file_write",
        description="Write a file within the workspace. Creates parent directories as needed. Consent required (destructive operation).",
        execute=lambda path, content, max_bytes=None: _file_write(base_dir, path, content, max_bytes),
        parameters={
            "path": "Relative file path (string)",
            "content": "File contents to write (string)",
            "max_bytes": "Maximum bytes to write (optional, default 1MB)"
        },
        consent=ConsentPolicy.REQUIRED,
        consent_category=ConsentCategory.DESTRUCTIVE,
        consent_context="Write file contents",
        side_effects=True,
    ))

    registry.register(Tool(
        name="file_edit",
        description="Edit a file by replacing the first occurrence of old with new. Generates unified diff. Consent required (destructive operation).",
        execute=lambda path, old, new: _file_edit(base_dir, path, old, new),
        parameters={
            "path": "Relative file path (string)",
            "old": "Anchor text to find (exact match required)",
            "new": "Replacement text"
        },
        consent=ConsentPolicy.REQUIRED,
        consent_category=ConsentCategory.DESTRUCTIVE,
        consent_context="Modify file contents",
        side_effects=True,
    ))

    registry.register(Tool(
        name="file_delete",
        description="Delete a file within the workspace. Consent required (destructive operation).",
        execute=lambda path: _file_delete(base_dir, path),
        parameters={
            "path": "Relative file path (string)"
        },
        consent=ConsentPolicy.REQUIRED,
        consent_category=ConsentCategory.DESTRUCTIVE,
        consent_context="Delete file",
        side_effects=True,
    ))

    registry.register(Tool(
        name="file_list",
        description="List files matching a glob pattern within the workspace. Respects depth/entry limits.",
        execute=lambda pattern="*", max_entries=None: _file_list(base_dir, pattern, max_entries),
        parameters={
            "pattern": "Glob pattern, e.g., '*.py' or 'src/**/*.ts' (default '*')",
            "max_entries": "Maximum entries to return (optional, default 500)"
        },
        consent=ConsentPolicy.NONE,
        side_effects=False,
    ))

    registry.register(Tool(
        name="file_grep",
        description="Search for text in files. Performs substring matching (not regex). Skips binary files and respects result limits.",
        execute=lambda pattern, file_pattern="**/*", max_results=None: _file_grep(base_dir, pattern, file_pattern, max_results),
        parameters={
            "pattern": "Substring to search for (string)",
            "file_pattern": "Glob pattern for files to search (default '**/*')",
            "max_results": "Maximum result lines to return (optional, default 1000)"
        },
        consent=ConsentPolicy.NONE,
        side_effects=False,
    ))

    registry.register(Tool(
        name="file_info",
        description="Get metadata about a file or directory (size, type, permissions, mtime). Does not read contents.",
        execute=lambda path: _file_info(base_dir, path),
        parameters={
            "path": "Relative file path (string)"
        },
        consent=ConsentPolicy.NONE,
        side_effects=False,
    ))
