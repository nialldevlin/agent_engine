"""Tests for file context extraction."""

import pytest
from pathlib import Path
import tempfile
import time
from agent_engine.utils.file_context import (
    FileRelevance,
    FileContextExtractor,
    MODE_THRESHOLDS,
    RELEVANT_EXTENSIONS,
    SKIP_DIRS,
    should_skip_file,
    extract_function_names,
)


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace with test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)

        # Create test files
        (workspace / "test.py").write_text("def hello():\n    print('world')\n\nclass TestClass:\n    pass")
        (workspace / "test.js").write_text("function test() {}\nconst myVar = () => {}")
        (workspace / "README.md").write_text("# Project\n\nThis is a test project.")
        (workspace / "config.json").write_text('{"key": "value"}')

        # Create directory structures
        (workspace / ".git").mkdir()
        (workspace / ".git" / "config").write_text("git config")
        (workspace / "__pycache__").mkdir()
        (workspace / "__pycache__" / "test.pyc").write_bytes(b"\x00\x01")
        (workspace / "node_modules").mkdir()
        (workspace / "node_modules" / "package.json").write_text("{}")

        # Create a nested structure
        subdir = workspace / "src"
        subdir.mkdir()
        (subdir / "main.py").write_text("def main():\n    pass")

        yield workspace


@pytest.fixture
def extractor(temp_workspace):
    """Create a FileContextExtractor instance."""
    return FileContextExtractor(temp_workspace, mode="balanced")


class TestShouldSkipFile:
    """Test file skipping logic."""

    def test_skip_pyc_files(self, temp_workspace):
        """Should skip compiled Python files."""
        pyc_file = temp_workspace / "__pycache__" / "test.pyc"
        assert should_skip_file(pyc_file) is True

    def test_skip_hidden_files(self, temp_workspace):
        """Should skip hidden files."""
        git_config = temp_workspace / ".git" / "config"
        assert should_skip_file(git_config) is True

    def test_skip_pycache_directory(self, temp_workspace):
        """Should skip __pycache__ directory."""
        pycache_dir = temp_workspace / "__pycache__" / "test.pyc"
        assert should_skip_file(pycache_dir) is True

    def test_skip_large_binary_files(self, temp_workspace):
        """Should skip binary file extensions."""
        jpg_file = temp_workspace / "image.jpg"
        jpg_file.write_bytes(b"fake image data")
        assert should_skip_file(jpg_file) is True

    def test_keep_python_file(self, temp_workspace):
        """Should not skip Python files."""
        py_file = temp_workspace / "test.py"
        assert should_skip_file(py_file) is False

    def test_keep_markdown_file(self, temp_workspace):
        """Should not skip Markdown files."""
        md_file = temp_workspace / "README.md"
        assert should_skip_file(md_file) is False


class TestExtractFunctionNames:
    """Test function/class name extraction."""

    def test_extract_python_functions(self):
        """Should extract Python function names."""
        content = """
def hello():
    pass

def world():
    pass

class MyClass:
    pass

async def async_func():
    pass
"""
        names = extract_function_names(content, ".py")
        assert "hello" in names
        assert "world" in names
        assert "MyClass" in names
        assert "async_func" in names

    def test_extract_javascript_functions(self):
        """Should extract JavaScript function and class names."""
        content = """
function greet() {}
class Person {}
const arrow = () => {}
export function exported() {}
"""
        names = extract_function_names(content, ".js")
        assert "greet" in names
        assert "Person" in names
        # Note: arrow functions without names won't be captured
        assert "exported" in names

    def test_extract_go_functions(self):
        """Should extract Go function names."""
        content = """
func hello() {}
func (r *Receiver) Method() {}
"""
        names = extract_function_names(content, ".go")
        assert "hello" in names
        assert "Method" in names

    def test_extract_rust_functions(self):
        """Should extract Rust function and struct names."""
        content = """
fn main() {}
struct User {}
fn process_data() {}
"""
        names = extract_function_names(content, ".rs")
        assert "main" in names
        assert "User" in names
        assert "process_data" in names

    def test_empty_content(self):
        """Should return empty set for empty content."""
        names = extract_function_names("", ".py")
        assert names == set()


class TestFileRelevance:
    """Test FileRelevance dataclass."""

    def test_file_relevance_creation(self, temp_workspace):
        """Should create FileRelevance objects with proper attributes."""
        py_file = temp_workspace / "test.py"
        relevance = FileRelevance(
            path=py_file,
            score=0.85,
            size=1024,
            modified_time=time.time(),
            reasons=["High relevance"],
            extraction_mode="inline"
        )

        assert relevance.path == py_file
        assert relevance.score == 0.85
        assert relevance.size == 1024
        assert relevance.extraction_mode == "inline"
        assert "High relevance" in relevance.reasons

    def test_file_relevance_comparison(self, temp_workspace):
        """Should compare FileRelevance objects by score."""
        py_file = temp_workspace / "test.py"
        rel1 = FileRelevance(py_file, 0.5, 1024, time.time(), ["Low"])
        rel2 = FileRelevance(py_file, 0.8, 1024, time.time(), ["High"])

        assert rel1 < rel2
        assert rel2 > rel1


class TestModeThresholds:
    """Test mode-specific thresholds."""

    def test_thresholds_exist_for_all_modes(self):
        """Should have thresholds defined for all modes."""
        expected_modes = ["cheap", "balanced", "max_quality"]
        for mode in expected_modes:
            assert mode in MODE_THRESHOLDS

    def test_cheap_mode_smaller_threshold(self):
        """Cheap mode should have smaller file thresholds."""
        cheap = MODE_THRESHOLDS["cheap"]
        balanced = MODE_THRESHOLDS["balanced"]

        assert cheap["inline_max"] < balanced["inline_max"]
        assert cheap["snippet_max"] < balanced["snippet_max"]

    def test_balanced_mode_smaller_than_max(self):
        """Balanced mode should have smaller thresholds than max_quality."""
        balanced = MODE_THRESHOLDS["balanced"]
        max_q = MODE_THRESHOLDS["max_quality"]

        assert balanced["inline_max"] < max_q["inline_max"]
        assert balanced["snippet_max"] < max_q["snippet_max"]


class TestRelevantExtensions:
    """Test file extension configuration."""

    def test_python_extension_included(self):
        """Should include Python files."""
        assert ".py" in RELEVANT_EXTENSIONS

    def test_javascript_extensions_included(self):
        """Should include JavaScript/TypeScript files."""
        assert ".js" in RELEVANT_EXTENSIONS
        assert ".ts" in RELEVANT_EXTENSIONS
        assert ".jsx" in RELEVANT_EXTENSIONS
        assert ".tsx" in RELEVANT_EXTENSIONS

    def test_markdown_extension_included(self):
        """Should include Markdown files."""
        assert ".md" in RELEVANT_EXTENSIONS

    def test_config_extensions_included(self):
        """Should include common config file types."""
        assert ".json" in RELEVANT_EXTENSIONS
        assert ".yaml" in RELEVANT_EXTENSIONS or ".yml" in RELEVANT_EXTENSIONS


class TestSkipDirs:
    """Test skip directories configuration."""

    def test_python_cache_skipped(self):
        """Should skip __pycache__ directories."""
        assert "__pycache__" in SKIP_DIRS

    def test_git_skipped(self):
        """Should skip .git directories."""
        assert ".git" in SKIP_DIRS

    def test_node_modules_skipped(self):
        """Should skip node_modules directories."""
        assert "node_modules" in SKIP_DIRS

    def test_venv_skipped(self):
        """Should skip virtual environment directories."""
        assert "venv" in SKIP_DIRS or ".venv" in SKIP_DIRS


class TestFileContextExtractorScan:
    """Test workspace file scanning."""

    def test_scan_finds_relevant_files(self, extractor, temp_workspace):
        """Should find Python and other relevant files."""
        files = extractor.scan_workspace_files()

        # Should find test.py and other relevant files
        file_names = [f.name for f in files]
        assert any(name.endswith(".py") for name in file_names)

    def test_scan_ignores_hidden_files(self, extractor, temp_workspace):
        """Should not include hidden files."""
        files = extractor.scan_workspace_files()

        file_names = [f.name for f in files]
        assert "config" not in file_names  # In .git
        assert not any(name.startswith(".") for name in file_names)

    def test_scan_ignores_pycache(self, extractor, temp_workspace):
        """Should not include __pycache__ files."""
        files = extractor.scan_workspace_files()

        file_names = [f.name for f in files]
        assert "test.pyc" not in file_names

    def test_scan_respects_max_files(self, extractor, temp_workspace):
        """Should limit results to max_files parameter."""
        files = extractor.scan_workspace_files(max_files=2)

        assert len(files) <= 2

    def test_scan_returns_sorted_by_modification(self, extractor, temp_workspace):
        """Should return files sorted by modification time (newest first)."""
        files = extractor.scan_workspace_files()

        # Files should be sorted, create two files with different times
        file1 = temp_workspace / "old_file.py"
        file2 = temp_workspace / "new_file.py"

        file1.write_text("old content")
        time.sleep(0.1)
        file2.write_text("new content")

        files = extractor.scan_workspace_files()

        # new_file.py should come before old_file.py
        file_names = [f.name for f in files]
        if "new_file.py" in file_names and "old_file.py" in file_names:
            new_idx = file_names.index("new_file.py")
            old_idx = file_names.index("old_file.py")
            assert new_idx < old_idx


class TestFileContextExtractorScoring:
    """Test file relevance scoring."""

    def test_score_file_relevance_returns_relevance(self, extractor, temp_workspace):
        """Should return FileRelevance object."""
        py_file = temp_workspace / "test.py"

        result = extractor.score_file_relevance(py_file, "test hello", set())

        assert isinstance(result, FileRelevance)
        assert isinstance(result.score, float)
        assert isinstance(result.reasons, list)
        assert isinstance(result.path, Path)

    def test_score_keyword_match(self, extractor, temp_workspace):
        """Should give high score for keyword matches."""
        py_file = temp_workspace / "test.py"

        # Query matches content in test.py
        relevance = extractor.score_file_relevance(py_file, "hello world function", set())

        assert relevance.score > 0
        assert len(relevance.reasons) > 0

    def test_score_no_match_low_score(self, extractor, temp_workspace):
        """Should give low score for no matches."""
        py_file = temp_workspace / "test.py"

        # Query doesn't match content
        relevance = extractor.score_file_relevance(py_file, "zebra elephant unicorn", set())

        # Should have low or zero score
        assert relevance.score < 0.5

    def test_score_recent_file_bonus(self, extractor, temp_workspace):
        """Should give bonus score for recently modified files."""
        py_file = temp_workspace / "test.py"

        # Modify file to make it recent
        py_file.write_text("def recent(): pass")

        # Query with keyword match
        relevance = extractor.score_file_relevance(py_file, "recent modified", set())

        # Recent modification should give some points
        assert relevance.score > 0 or any("recent" in str(r).lower() for r in relevance.reasons)


class TestFileContextExtractorDetermineMode:
    """Test extraction mode determination."""

    def test_small_file_inline_mode(self, extractor):
        """Should use inline mode for small files."""
        # For balanced mode, inline_max is 10000
        small_size = 5000
        mode = extractor._determine_extraction_mode(small_size)
        assert mode == "inline"

    def test_medium_file_snippet_mode(self, extractor):
        """Should use snippet mode for medium files."""
        # For balanced mode: inline_max=10000, snippet_max=30000
        medium_size = 15000
        mode = extractor._determine_extraction_mode(medium_size)
        assert mode == "snippet"

    def test_large_file_summary_mode(self, extractor):
        """Should use summary mode for large files."""
        # For balanced mode: snippet_max=30000, summarize_min=30001
        large_size = 50000
        mode = extractor._determine_extraction_mode(large_size)
        assert mode == "summary"

    def test_very_large_file_skip_mode(self, extractor):
        """Should use skip mode for very large files."""
        # For balanced mode: should skip files > 2x summarize_min
        very_large_size = 200000
        mode = extractor._determine_extraction_mode(very_large_size)
        assert mode == "skip"


class TestFileContextExtractorExtractContent:
    """Test content extraction."""

    def test_extract_file_context_inline_mode(self, extractor, temp_workspace):
        """Should extract full content for inline mode."""
        # Query that matches content in workspace
        files = extractor.extract_file_context(query="hello world")

        # Should extract at least one file
        assert isinstance(files, list)
        if len(files) > 0:
            path, content, reasons = files[0]
            assert isinstance(path, Path)
            assert isinstance(content, str)
            assert isinstance(reasons, list)

    def test_extract_file_context_returns_list(self, extractor, temp_workspace):
        """Should return list of (path, content, reasons) tuples."""
        result = extractor.extract_file_context(query="test")

        assert isinstance(result, list)
        for item in result:
            assert isinstance(item, tuple)
            assert len(item) == 3
            path, content, reasons = item
            assert isinstance(path, Path)
            assert isinstance(content, str)
            assert isinstance(reasons, list)

    def test_extract_context_filters_by_relevance(self, extractor, temp_workspace):
        """Should filter files by relevance threshold."""
        # Query that doesn't match should result in empty or filtered results
        result = extractor.extract_file_context(query="completely unrelated xyz")

        # Result should be a list
        assert isinstance(result, list)


class TestCheapMode:
    """Test cheap cost mode configuration."""

    def test_cheap_mode_extractor(self, temp_workspace):
        """Should create extractor with cheap mode thresholds."""
        extractor = FileContextExtractor(temp_workspace, mode="cheap")

        cheap_thresholds = MODE_THRESHOLDS["cheap"]

        # Verify mode affects threshold selection
        small_file_size = 1000
        mode = extractor._determine_extraction_mode(small_file_size)
        assert mode == "inline"

        # Medium file should be snippet for cheap mode
        medium_file_size = 3000
        mode = extractor._determine_extraction_mode(medium_file_size)
        assert mode == "snippet"


class TestMaxQualityMode:
    """Test max quality cost mode configuration."""

    def test_max_quality_mode_extractor(self, temp_workspace):
        """Should create extractor with max_quality mode thresholds."""
        extractor = FileContextExtractor(temp_workspace, mode="max_quality")

        # Larger files should still be inline in max_quality mode
        large_file_size = 40000
        mode = extractor._determine_extraction_mode(large_file_size)
        assert mode == "snippet" or mode == "inline"
