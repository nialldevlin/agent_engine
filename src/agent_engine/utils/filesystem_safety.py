"""Filesystem safety utilities for Agent Engine.

Provides path traversal validation, binary file detection, and safe file
operation helpers. These utilities ensure that filesystem operations remain
within safe boundaries and prevent attacks like directory traversal.

Design principles:
- Path traversal prevention through validation and resolution
- Binary file detection by extension and content sampling
- Clear separation of validation logic from tool implementation
- Explicit configuration constants for easy adjustment
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Set, Tuple

# Configuration constants for limits and validation
DEFAULT_MAX_READ_BYTES = 50_000  # Default max bytes for file read operations
DEFAULT_MAX_WRITE_BYTES = 1_000_000  # Default max bytes for file write operations

# Binary file extensions to skip (covers compiled formats, images, audio, video, archives, documents, etc.)
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


def validate_path_traversal(
    workspace_root: Path,
    target_path: str
) -> Tuple[bool, Optional[str], Optional[Path]]:
    """Validate that a target path does not escape the workspace root.

    Prevents path traversal attacks by ensuring that the resolved target path
    remains within the workspace root directory. Uses absolute path resolution
    and relative path validation.

    Args:
        workspace_root: Base directory (workspace root).
        target_path: Target path to validate (can be relative or absolute).

    Returns:
        Tuple of (is_valid, error_message, resolved_path):
        - is_valid: True if path is safe, False otherwise.
        - error_message: Human-readable error message if invalid, None if valid.
        - resolved_path: Resolved Path object if valid, None if invalid.

    Examples:
        >>> root = Path("/workspace")
        >>> is_valid, err, path = validate_path_traversal(root, "file.txt")
        >>> if is_valid:
        ...     print(path)  # /workspace/file.txt

        >>> is_valid, err, path = validate_path_traversal(root, "../../../etc/passwd")
        >>> if not is_valid:
        ...     print(err)  # Path traversal detected: ... escapes workspace
    """
    try:
        base = workspace_root.resolve()
        candidate = (base / target_path).resolve()
        # This raises ValueError if candidate is not within base
        candidate.relative_to(base)
        return True, None, candidate
    except ValueError:
        return False, f"Path traversal detected: {target_path} escapes workspace", None
    except Exception as e:
        return False, f"Invalid path: {str(e)}", None


def is_binary_file(path: Path) -> bool:
    """Check if a file is likely binary based on extension and content sampling.

    Uses a two-stage detection approach:
    1. Fast check: examine file extension against known binary extensions
    2. Content check: sample first 512 bytes for null bytes (binary signature)

    Args:
        path: Path to the file to check.

    Returns:
        True if the file is likely binary, False if likely text.

    Examples:
        >>> is_binary_file(Path("image.png"))
        True

        >>> is_binary_file(Path("script.py"))
        False
    """
    # Check extension first (fast path)
    if path.suffix.lower() in SKIP_EXTENSIONS:
        return True

    # Sample first 512 bytes to detect binary content
    try:
        with open(path, "rb") as f:
            chunk = f.read(512)
            # Presence of null byte is strong indicator of binary content
            if b"\x00" in chunk:
                return True
    except Exception:
        # If we can't read it, assume it's not binary to avoid false positives
        # on permission-denied scenarios
        pass

    return False
