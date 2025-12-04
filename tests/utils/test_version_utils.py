"""Tests for version utilities."""

import pytest
from agent_engine.utils.version_utils import (
    parse_version,
    compare_versions,
    is_compatible,
)


class TestParseVersion:
    """Tests for parse_version function."""

    def test_valid_full_version(self):
        """Parse full semantic version."""
        result = parse_version("1.2.3")
        assert result == (1, 2, 3)

    def test_major_only(self):
        """Parse major version only."""
        result = parse_version("2")
        assert result == (2, 0, 0)

    def test_major_minor(self):
        """Parse major and minor version."""
        result = parse_version("3.1")
        assert result == (3, 1, 0)

    def test_major_minor_patch(self):
        """Parse full semantic version."""
        result = parse_version("1.2.3")
        assert result == (1, 2, 3)

    def test_zero_versions(self):
        """Parse versions with zeros."""
        result = parse_version("0.0.0")
        assert result == (0, 0, 0)

    def test_large_version_numbers(self):
        """Parse large version numbers."""
        result = parse_version("100.200.300")
        assert result == (100, 200, 300)

    def test_none_input(self):
        """None input should return (0, 0, 0)."""
        result = parse_version(None)
        assert result == (0, 0, 0)

    def test_empty_string(self):
        """Empty string should return (0, 0, 0)."""
        result = parse_version("")
        assert result == (0, 0, 0)

    def test_invalid_non_numeric(self):
        """Invalid non-numeric string should return (0, 0, 0)."""
        result = parse_version("invalid")
        assert result == (0, 0, 0)

    def test_invalid_mixed_content(self):
        """Mixed numeric and non-numeric should return (0, 0, 0)."""
        result = parse_version("1.a.3")
        assert result == (0, 0, 0)

    def test_invalid_empty_parts(self):
        """Empty parts should return (0, 0, 0)."""
        result = parse_version("1..3")
        assert result == (0, 0, 0)

    def test_extra_version_parts(self):
        """Extra version parts beyond patch should be ignored."""
        result = parse_version("1.2.3.4.5")
        assert result == (1, 2, 3)

    def test_version_with_whitespace(self):
        """Version strings with whitespace should fail gracefully."""
        result = parse_version("1.2.3 ")
        # Will return (0, 0, 0) or handle gracefully
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_non_string_input(self):
        """Non-string input should return (0, 0, 0)."""
        result = parse_version(123)
        assert result == (0, 0, 0)

    def test_list_input(self):
        """List input should return (0, 0, 0)."""
        result = parse_version([1, 2, 3])
        assert result == (0, 0, 0)


class TestCompareVersions:
    """Tests for compare_versions function."""

    def test_equal_versions(self):
        """Identical versions should return 0."""
        assert compare_versions("1.2.3", "1.2.3") == 0

    def test_version1_greater(self):
        """version1 > version2 should return 1."""
        assert compare_versions("2.0.0", "1.9.9") == 1

    def test_version1_less(self):
        """version1 < version2 should return -1."""
        assert compare_versions("1.2.3", "1.3.0") == -1

    def test_major_version_difference(self):
        """Different major versions."""
        assert compare_versions("2.0.0", "1.0.0") == 1
        assert compare_versions("1.0.0", "2.0.0") == -1

    def test_minor_version_difference(self):
        """Different minor versions with same major."""
        assert compare_versions("1.5.0", "1.2.0") == 1
        assert compare_versions("1.2.0", "1.5.0") == -1

    def test_patch_version_difference(self):
        """Different patch versions."""
        assert compare_versions("1.2.5", "1.2.3") == 1
        assert compare_versions("1.2.3", "1.2.5") == -1

    def test_incomplete_versions(self):
        """Compare incomplete versions (implicit zeros)."""
        assert compare_versions("1.2", "1.2.0") == 0
        assert compare_versions("1", "1.0.0") == 0

    def test_version_with_invalid_parts(self):
        """Invalid parts parse as (0, 0, 0)."""
        result = compare_versions("invalid", "1.0.0")
        assert result == -1  # (0,0,0) < (1,0,0)

    def test_zero_versions(self):
        """Compare zero versions."""
        assert compare_versions("0.0.0", "0.0.0") == 0
        assert compare_versions("0.1.0", "0.0.1") == 1

    def test_large_version_numbers(self):
        """Compare large version numbers."""
        assert compare_versions("100.200.300", "100.200.300") == 0
        assert compare_versions("100.200.301", "100.200.300") == 1

    def test_comparison_is_transitive(self):
        """Version comparison should be transitive."""
        # If a < b and b < c, then a < c
        a = "1.0.0"
        b = "1.5.0"
        c = "2.0.0"

        assert compare_versions(a, b) == -1
        assert compare_versions(b, c) == -1
        assert compare_versions(a, c) == -1

    def test_single_digit_versions(self):
        """Compare single digit versions."""
        assert compare_versions("1", "2") == -1
        assert compare_versions("2", "1") == 1
        assert compare_versions("1", "1") == 0

    def test_mixed_length_versions(self):
        """Compare versions with different numbers of parts."""
        # 1.2.3 > 1.2.0 (1.2 is parsed as 1.2.0)
        assert compare_versions("1.2.3", "1.2") == 1
        assert compare_versions("1.2", "1.2.1") == -1
        # Same major.minor should be equal
        assert compare_versions("1.2", "1.2.0") == 0


class TestIsCompatible:
    """Tests for is_compatible function."""

    def test_same_major_version(self):
        """Same major version should be compatible."""
        assert is_compatible("1.5.0", "1.2.0") is True

    def test_different_major_version(self):
        """Different major versions are not compatible."""
        assert is_compatible("2.0.0", "1.5.0") is False
        assert is_compatible("1.5.0", "2.0.0") is False

    def test_exact_match(self):
        """Exact version match should be compatible."""
        assert is_compatible("1.2.3", "1.2.3") is True

    def test_agent_minor_greater(self):
        """Agent with greater minor version should be compatible."""
        assert is_compatible("1.5.0", "1.2.0") is True

    def test_agent_minor_equal(self):
        """Agent with equal minor version should be compatible."""
        assert is_compatible("1.2.0", "1.2.0") is True

    def test_agent_minor_less(self):
        """Agent with lesser minor version should not be compatible."""
        assert is_compatible("1.2.0", "1.5.0") is False

    def test_patch_version_ignored(self):
        """Patch version should be ignored in compatibility check."""
        assert is_compatible("1.2.5", "1.2.0") is True
        assert is_compatible("1.2.0", "1.2.5") is True

    def test_zero_versions(self):
        """Zero versions should work correctly."""
        assert is_compatible("0.0.0", "0.0.0") is True
        assert is_compatible("0.1.0", "0.0.0") is True
        assert is_compatible("0.0.1", "0.1.0") is False

    def test_major_zero_minor_difference(self):
        """Major 0 with minor differences."""
        assert is_compatible("0.5.0", "0.2.0") is True
        assert is_compatible("0.2.0", "0.5.0") is False

    def test_major_one_versions(self):
        """Major version 1 compatibility."""
        assert is_compatible("1.0.0", "1.0.0") is True
        assert is_compatible("1.1.0", "1.0.0") is True
        assert is_compatible("1.0.0", "1.1.0") is False

    def test_major_large_numbers(self):
        """Large major version numbers."""
        assert is_compatible("100.50.0", "100.40.0") is True
        assert is_compatible("99.50.0", "100.40.0") is False

    def test_invalid_version_strings(self):
        """Invalid version strings parsed as (0, 0, 0)."""
        result = is_compatible("invalid", "0.0.0")
        assert result is True  # (0,0,0) compatible with (0,0,0)

    def test_empty_version_strings(self):
        """Empty version strings parsed as (0, 0, 0)."""
        assert is_compatible("", "") is True

    def test_incomplete_versions(self):
        """Incomplete versions with implicit zeros."""
        assert is_compatible("1.2", "1.0") is True
        assert is_compatible("1", "1.5") is False
        assert is_compatible("1.0", "1") is True

    def test_semantic_versioning_spec(self):
        """Test semantic versioning compatibility rules.

        Following semver: A version is compatible if:
        - Major version is the same
        - Agent minor version >= required minor version
        - Patch version is irrelevant
        """
        # Compatible scenarios
        assert is_compatible("2.3.1", "2.3.0") is True  # same major/minor
        assert is_compatible("2.4.0", "2.3.0") is True  # agent minor > required
        assert is_compatible("2.5.10", "2.2.5") is True  # agent minor > required

        # Incompatible scenarios
        assert is_compatible("2.2.0", "2.3.0") is False  # agent minor < required
        assert is_compatible("1.5.0", "2.1.0") is False  # different major
        assert is_compatible("3.0.0", "2.9.9") is False  # different major
