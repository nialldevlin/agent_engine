"""Tests for filesystem safety utilities."""

import pytest
from pathlib import Path
import tempfile
from agent_engine.utils.filesystem_safety import (
    validate_path_traversal,
    is_binary_file,
    SKIP_EXTENSIONS,
)


@pytest.fixture
def temp_workspace():
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        yield workspace


def test_validate_path_traversal_safe(temp_workspace):
    is_valid, error, resolved = validate_path_traversal(
        temp_workspace, "safe/file.txt"
    )
    assert is_valid is True
    assert error is None
    assert resolved is not None


def test_validate_path_traversal_escape_dotdot(temp_workspace):
    is_valid, error, resolved = validate_path_traversal(
        temp_workspace, "../../../etc/passwd"
    )
    assert is_valid is False
    assert "traversal" in error.lower()


def test_validate_path_traversal_absolute(temp_workspace):
    is_valid, error, resolved = validate_path_traversal(
        temp_workspace, "/etc/passwd"
    )
    # Absolute paths outside workspace should fail
    assert is_valid is False


def test_is_binary_file_by_extension(temp_workspace):
    # Create test files
    text_file = temp_workspace / "test.txt"
    binary_file = temp_workspace / "test.png"

    text_file.write_text("Hello world")
    binary_file.write_bytes(b"\x89PNG\r\n")

    assert is_binary_file(text_file) is False
    assert is_binary_file(binary_file) is True


def test_is_binary_file_by_content(temp_workspace):
    # File with text extension but binary content
    fake_text = temp_workspace / "fake.txt"
    fake_text.write_bytes(b"\x00\x01\x02\x03")

    # Should detect null bytes
    assert is_binary_file(fake_text) is True


def test_skip_extensions_contains_common():
    # Verify SKIP_EXTENSIONS has common binaries
    assert ".pyc" in SKIP_EXTENSIONS
    assert ".png" in SKIP_EXTENSIONS
    assert ".exe" in SKIP_EXTENSIONS or ".bin" in SKIP_EXTENSIONS
