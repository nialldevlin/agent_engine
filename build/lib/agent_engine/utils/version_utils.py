"""
Toolkit helpers for parsing semantic versions and checking compatibility.
"""

from __future__ import annotations

from typing import Tuple, Union


def parse_version(version_str: Union[str, None]) -> Tuple[int, int, int]:
    """Parse a semantic version string into a (major, minor, patch) tuple."""

    if not version_str or not isinstance(version_str, str):
        return 0, 0, 0

    parts = version_str.split(".")
    try:
        major = int(parts[0]) if len(parts) > 0 else 0
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2]) if len(parts) > 2 else 0
        return major, minor, patch
    except ValueError:
        return 0, 0, 0


def compare_versions(version1: str, version2: str) -> int:
    """Compare two semantic versions, returning -1, 0, or 1."""

    v1 = parse_version(version1)
    v2 = parse_version(version2)
    if v1 < v2:
        return -1
    if v1 > v2:
        return 1
    return 0


def is_compatible(agent_schema: str, required_schema: str) -> bool:
    """Check schema compatibility (same major version and minor >= required)."""

    agent_v = parse_version(agent_schema)
    required_v = parse_version(required_schema)
    if agent_v[0] != required_v[0]:
        return False
    if agent_v[1] < required_v[1]:
        return False
    return True


__all__ = ["parse_version", "compare_versions", "is_compatible"]
