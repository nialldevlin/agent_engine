"""Verification tests for extracted filesystem safety and JSON I/O utilities.

This test module validates:
1. Path traversal attack prevention
2. Binary file detection
3. JSON safe read/write operations
4. JSON structure validation
"""

import json
import tempfile
from pathlib import Path

from agent_engine.utils import (
    validate_path_traversal,
    is_binary_file,
    DEFAULT_MAX_READ_BYTES,
    DEFAULT_MAX_WRITE_BYTES,
    read_json_safe,
    write_json_safe,
    validate_json_structure,
)
from agent_engine.utils.filesystem_safety import SKIP_EXTENSIONS


def test_validate_path_traversal():
    """Test path traversal attack prevention."""
    workspace = Path("/workspace")

    # Test 1: Valid path within workspace
    is_valid, err, resolved = validate_path_traversal(workspace, "file.txt")
    assert is_valid, f"Valid path rejected: {err}"
    assert resolved is not None
    assert "file.txt" in str(resolved)

    # Test 2: Nested valid path
    is_valid, err, resolved = validate_path_traversal(workspace, "src/main.py")
    assert is_valid, f"Valid nested path rejected: {err}"
    assert resolved is not None

    # Test 3: Path traversal attack
    is_valid, err, resolved = validate_path_traversal(workspace, "../../../etc/passwd")
    assert not is_valid, "Path traversal attack was NOT blocked!"
    assert "traversal detected" in err.lower()
    assert resolved is None

    # Test 4: Absolute path attack
    is_valid, err, resolved = validate_path_traversal(workspace, "/etc/passwd")
    assert not is_valid, "Absolute path escape was NOT blocked!"
    assert resolved is None

    print("Path traversal validation: PASS")


def test_is_binary_file():
    """Test binary file detection."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Test 1: Text file
        text_file = tmpdir / "script.py"
        text_file.write_text("print('hello')\n")
        assert not is_binary_file(text_file), "Text file incorrectly detected as binary"

        # Test 2: Binary extension (PNG stub)
        png_file = tmpdir / "image.png"
        png_file.write_bytes(b"\x89PNG\r\n\x1a\n")
        assert is_binary_file(png_file), "PNG file not detected as binary"

        # Test 3: Known binary extension
        pyc_file = tmpdir / "compiled.pyc"
        pyc_file.write_bytes(b"bytecode")
        assert is_binary_file(pyc_file), ".pyc file not detected as binary by extension"

        # Test 4: Text file with binary extension (edge case)
        fake_binary = tmpdir / "fake.exe"
        fake_binary.write_text("not really binary\n")
        # This should be detected as binary by extension alone
        assert is_binary_file(fake_binary), ".exe extension not recognized"

        # Test 5: Null byte in content
        null_file = tmpdir / "with_null.txt"
        null_file.write_bytes(b"some text\x00more text")
        assert is_binary_file(null_file), "File with null byte not detected as binary"

    print("Binary file detection: PASS")


def test_skip_extensions():
    """Test that SKIP_EXTENSIONS contains expected extensions."""
    # Verify some common extensions are present
    assert ".pyc" in SKIP_EXTENSIONS, ".pyc not in SKIP_EXTENSIONS"
    assert ".jpg" in SKIP_EXTENSIONS, ".jpg not in SKIP_EXTENSIONS"
    assert ".pdf" in SKIP_EXTENSIONS, ".pdf not in SKIP_EXTENSIONS"
    assert ".zip" in SKIP_EXTENSIONS, ".zip not in SKIP_EXTENSIONS"

    # Verify it's a set
    assert isinstance(SKIP_EXTENSIONS, set), "SKIP_EXTENSIONS should be a set"

    print("SKIP_EXTENSIONS constant: PASS")


def test_constants():
    """Test configuration constants."""
    assert DEFAULT_MAX_READ_BYTES == 50_000, "DEFAULT_MAX_READ_BYTES incorrect"
    assert DEFAULT_MAX_WRITE_BYTES == 1_000_000, "DEFAULT_MAX_WRITE_BYTES incorrect"
    assert isinstance(DEFAULT_MAX_READ_BYTES, int)
    assert isinstance(DEFAULT_MAX_WRITE_BYTES, int)

    print("Configuration constants: PASS")


def test_read_json_safe():
    """Test safe JSON reading with error handling."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Test 1: Read valid JSON
        valid_json = tmpdir / "valid.json"
        test_data = {"name": "test", "value": 42}
        valid_json.write_text(json.dumps(test_data))

        data, err = read_json_safe(valid_json)
        assert err is None, f"Valid JSON read failed: {err}"
        assert data == test_data, f"JSON data mismatch: {data} != {test_data}"

        # Test 2: Read missing file
        missing_file = tmpdir / "missing.json"
        default_val = {"default": True}
        data, err = read_json_safe(missing_file, default=default_val)
        assert err is not None, "Error message should be set for missing file"
        assert data == default_val, "Default value not returned for missing file"
        assert "not found" in err.lower()

        # Test 3: Read malformed JSON
        bad_json = tmpdir / "bad.json"
        bad_json.write_text("{invalid json content")

        data, err = read_json_safe(bad_json, default={})
        assert err is not None, "Error message should be set for bad JSON"
        assert data == {}, "Default should be returned for bad JSON"
        assert "parse" in err.lower()

    print("JSON safe read: PASS")


def test_write_json_safe():
    """Test safe JSON writing with directory creation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Test 1: Write JSON to existing directory
        json_file = tmpdir / "output.json"
        data = {"test": "value", "number": 123}

        success, err = write_json_safe(json_file, data)
        assert success, f"Write failed: {err}"
        assert err is None, f"Error should be None on success: {err}"
        assert json_file.exists(), "JSON file was not created"

        # Verify written content
        written_data = json.loads(json_file.read_text())
        assert written_data == data, f"Written data mismatch: {written_data} != {data}"

        # Test 2: Write JSON with nested directories (auto-create)
        nested_file = tmpdir / "deep" / "nested" / "path" / "config.json"
        nested_data = {"nested": True}

        success, err = write_json_safe(nested_file, nested_data)
        assert success, f"Nested write failed: {err}"
        assert nested_file.exists(), "Nested JSON file was not created"

        # Verify directories were created
        assert nested_file.parent.exists(), "Parent directories not created"

        # Test 3: Write non-ASCII content
        non_ascii_file = tmpdir / "unicode.json"
        unicode_data = {"greeting": "Hello 世界", "emoji": ""}

        success, err = write_json_safe(non_ascii_file, unicode_data, ensure_ascii=False)
        assert success, f"Unicode write failed: {err}"

        # Verify unicode is preserved
        written = json.loads(non_ascii_file.read_text())
        assert written["greeting"] == "Hello 世界", "Unicode content lost"

    print("JSON safe write: PASS")


def test_validate_json_structure():
    """Test JSON structure validation."""
    # Test 1: Valid structure with all required keys
    data = {"name": "Alice", "age": 30, "email": "alice@example.com"}
    is_valid, missing = validate_json_structure(data, ["name", "age"])
    assert is_valid, f"Valid structure rejected: missing={missing}"
    assert missing == [], f"No keys should be missing: {missing}"

    # Test 2: Missing keys
    is_valid, missing = validate_json_structure(data, ["name", "age", "phone"])
    assert not is_valid, "Invalid structure accepted"
    assert "phone" in missing, f"Missing 'phone' not reported: {missing}"
    assert missing == ["phone"], f"Unexpected missing keys: {missing}"

    # Test 3: Multiple missing keys
    is_valid, missing = validate_json_structure(data, ["name", "phone", "address"])
    assert not is_valid, "Invalid structure accepted"
    assert len(missing) == 2, f"Should have 2 missing keys: {missing}"
    assert set(missing) == {"phone", "address"}, f"Wrong missing keys: {missing}"

    # Test 4: Non-dict data
    is_valid, missing = validate_json_structure([1, 2, 3], ["key"])
    assert not is_valid, "Non-dict data accepted as valid"
    assert missing == ["Data is not an object"], f"Wrong error for non-dict: {missing}"

    # Test 5: None as data
    is_valid, missing = validate_json_structure(None, ["key"])
    assert not is_valid, "None accepted as valid"
    assert missing == ["Data is not an object"], f"Wrong error for None: {missing}"

    # Test 6: Empty required keys
    is_valid, missing = validate_json_structure(data, [])
    assert is_valid, "Valid structure with no required keys rejected"
    assert missing == [], "Empty required list should have no missing keys"

    print("JSON structure validation: PASS")


def main():
    """Run all verification tests."""
    print("=" * 60)
    print("VERIFICATION TESTS FOR EXTRACTED UTILITIES")
    print("=" * 60)
    print()

    try:
        test_validate_path_traversal()
        test_is_binary_file()
        test_skip_extensions()
        test_constants()
        test_read_json_safe()
        test_write_json_safe()
        test_validate_json_structure()

        print()
        print("=" * 60)
        print("ALL TESTS PASSED!")
        print("=" * 60)
        return 0
    except AssertionError as e:
        print()
        print("=" * 60)
        print(f"TEST FAILED: {e}")
        print("=" * 60)
        return 1
    except Exception as e:
        print()
        print("=" * 60)
        print(f"UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 60)
        return 2


if __name__ == "__main__":
    exit(main())
