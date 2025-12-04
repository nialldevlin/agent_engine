"""Tests for logging utilities."""

import pytest
from pathlib import Path
import tempfile
from agent_engine.utils.logging_utils import (
    auto_cleanup_empty_log,
    safe_append_log,
    rotate_log_if_needed,
)


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test_safe_append_log_creates_file(temp_dir):
    log_file = temp_dir / "test.log"

    success, error = safe_append_log(log_file, "First line")

    assert success is True
    assert error is None
    assert log_file.exists()
    assert "First line" in log_file.read_text()


def test_safe_append_log_appends(temp_dir):
    log_file = temp_dir / "test.log"
    log_file.write_text("Existing content\n")

    success, error = safe_append_log(log_file, "New line")

    assert success is True
    content = log_file.read_text()
    assert "Existing content" in content
    assert "New line" in content


def test_safe_append_log_creates_dirs(temp_dir):
    log_file = temp_dir / "nested" / "logs" / "test.log"

    success, error = safe_append_log(log_file, "Test")

    assert success is True
    assert log_file.exists()


def test_safe_append_log_trailing_newline(temp_dir):
    log_file = temp_dir / "test.log"

    safe_append_log(log_file, "Line without newline", ensure_trailing_newline=True)

    content = log_file.read_text()
    assert content.endswith("\n")


def test_rotate_log_if_needed_under_limit(temp_dir):
    log_file = temp_dir / "test.log"
    log_file.write_text("Small content")

    success, error, metadata = rotate_log_if_needed(log_file, max_size=1000)

    assert success is True
    assert metadata.get("status") == "Log size within threshold"


def test_rotate_log_if_needed_over_limit(temp_dir):
    log_file = temp_dir / "test.log"
    log_file.write_text("a" * 2000)

    success, error, metadata = rotate_log_if_needed(log_file, max_size=1000, keep_count=2)

    assert success is True
    assert metadata.get("status") == "Log rotated"
    # Should create .1 archive
    assert (temp_dir / "test.log.1").exists()


def test_auto_cleanup_empty_log_removes(temp_dir):
    log_file = temp_dir / "empty.log"
    log_file.write_text("")

    result = auto_cleanup_empty_log(log_file, lambda p: p.stat().st_size == 0)

    assert result is True
    assert not log_file.exists()


def test_auto_cleanup_empty_log_keeps_non_empty(temp_dir):
    log_file = temp_dir / "nonempty.log"
    log_file.write_text("Content")

    result = auto_cleanup_empty_log(log_file, lambda p: p.stat().st_size == 0)

    assert result is False
    assert log_file.exists()
