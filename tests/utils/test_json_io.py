"""Tests for JSON I/O utilities."""

import pytest
from pathlib import Path
import tempfile
import json
from agent_engine.utils.json_io import (
    read_json_safe,
    write_json_safe,
    validate_json_structure,
)


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test_read_json_safe_valid(temp_dir):
    json_file = temp_dir / "test.json"
    data = {"key": "value", "number": 42}
    json_file.write_text(json.dumps(data))

    result, error = read_json_safe(json_file)
    assert error is None
    assert result == data


def test_read_json_safe_missing_file(temp_dir):
    json_file = temp_dir / "missing.json"
    default = {"default": True}

    result, error = read_json_safe(json_file, default=default)
    assert result == default
    assert error is not None


def test_read_json_safe_corrupt(temp_dir):
    json_file = temp_dir / "corrupt.json"
    json_file.write_text("{ invalid json }")

    result, error = read_json_safe(json_file, default={})
    assert result == {}
    assert error is not None
    assert "json" in error.lower()


def test_write_json_safe_creates_dirs(temp_dir):
    json_file = temp_dir / "nested" / "dir" / "test.json"
    data = {"test": "data"}

    success, error = write_json_safe(json_file, data)

    assert success is True
    assert error is None
    assert json_file.exists()
    assert json.loads(json_file.read_text()) == data


def test_write_json_safe_overwrites(temp_dir):
    json_file = temp_dir / "test.json"
    json_file.write_text('{"old": "data"}')

    new_data = {"new": "data"}
    success, error = write_json_safe(json_file, new_data)

    assert success is True
    assert json.loads(json_file.read_text()) == new_data


def test_validate_json_structure_valid():
    data = {"name": "test", "version": "1.0", "extra": "field"}
    required = ["name", "version"]

    is_valid, missing = validate_json_structure(data, required)

    assert is_valid is True
    assert missing == []


def test_validate_json_structure_missing():
    data = {"name": "test"}
    required = ["name", "version", "author"]

    is_valid, missing = validate_json_structure(data, required)

    assert is_valid is False
    assert "version" in missing
    assert "author" in missing
