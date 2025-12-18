"""File context extraction for Agent Engine - Intelligent workspace file inclusion.

Auto-include relevant files based on query and conversation.

Based on research of extraction strategies:
- Inline full file if small
- Extract referenced symbols/functions for medium files
- Summarize or use embedding search for large files
- Mode-dependent thresholds

Relevance scoring considers:
- Keyword overlap with query
- File mentions in recent conversation
- File modification recency
- File type and extension
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Tuple
from pathlib import Path
import os
import re
import logging
from datetime import datetime

from agent_engine.utils.text_analysis import extract_keywords

logger = logging.getLogger(__name__)


# File size thresholds per mode (in bytes)
MODE_THRESHOLDS = {
    "cheap": {
        "inline_max": 2000,      # 2KB - very small files only
        "snippet_max": 5000,     # 5KB - extract snippets
        "summarize_min": 5001,   # >5KB - summarize
    },
    "balanced": {
        "inline_max": 10000,     # 10KB - small files
        "snippet_max": 30000,    # 30KB - extract snippets
        "summarize_min": 30001,  # >30KB - summarize
    },
    "max_quality": {
        "inline_max": 50000,     # 50KB - medium files
        "snippet_max": 100000,   # 100KB - extract snippets
        "summarize_min": 100001, # >100KB - summarize
    },
}

# Relevant file extensions (code, config, docs)
RELEVANT_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java", ".c", ".cpp", ".h",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".md", ".txt", ".rst",
    ".sh", ".bash", ".zsh",
    ".sql", ".graphql",
    ".html", ".css", ".scss",
}

# Binary/irrelevant extensions to skip
SKIP_EXTENSIONS = {
    ".pyc", ".pyo", ".pyd", ".so", ".dll", ".dylib",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg",
    ".pdf", ".zip", ".tar", ".gz", ".bz2", ".xz",
    ".exe", ".bin", ".o", ".a",
    ".woff", ".woff2", ".ttf", ".eot",
}

# Skip directories
SKIP_DIRS = {
    "__pycache__", "node_modules", ".git", ".venv", "venv",
    "build", "dist", ".pytest_cache", ".mypy_cache",
    "coverage", ".coverage", "htmlcov",
}


def should_skip_file(file_path: Path) -> bool:
    """
    Determine if a file should be skipped from context.

    Args:
        file_path: Path to file

    Returns:
        True if file should be skipped
    """
    # Skip by extension
    if file_path.suffix.lower() in SKIP_EXTENSIONS:
        return True

    # Skip hidden files/directories
    if any(part.startswith('.') for part in file_path.parts):
        return True

    # Skip common directories
    if any(part in SKIP_DIRS for part in file_path.parts):
        return True

    return False


def extract_function_names(content: str, file_ext: str) -> Set[str]:
    """
    Extract function/class names from code.

    Simple regex-based extraction for common patterns.

    Args:
        content: File content
        file_ext: File extension (e.g., ".py", ".js")

    Returns:
        Set of function/class names
    """
    names = set()

    if file_ext == ".py":
        # Python: def function_name, class ClassName
        names.update(re.findall(r'^\s*def\s+(\w+)', content, re.MULTILINE))
        names.update(re.findall(r'^\s*class\s+(\w+)', content, re.MULTILINE))
        names.update(re.findall(r'^\s*async\s+def\s+(\w+)', content, re.MULTILINE))

    elif file_ext in {".js", ".ts", ".jsx", ".tsx"}:
        # JavaScript/TypeScript: function name, class Name, const name =
        names.update(re.findall(r'\bfunction\s+(\w+)', content))
        names.update(re.findall(r'\bclass\s+(\w+)', content))
        names.update(re.findall(r'\bconst\s+(\w+)\s*=\s*(?:async\s*)?\(', content))
        names.update(re.findall(r'\bexport\s+(?:async\s+)?function\s+(\w+)', content))

    elif file_ext in {".go"}:
        # Go: func FunctionName
        names.update(re.findall(r'\bfunc\s+(?:\([^)]*\)\s+)?(\w+)', content))

    elif file_ext in {".rs"}:
        # Rust: fn function_name, struct StructName
        names.update(re.findall(r'\bfn\s+(\w+)', content))
        names.update(re.findall(r'\bstruct\s+(\w+)', content))

    return names


@dataclass
class FileRelevance:
    """
    Relevance score and metadata for a workspace file.

    Attributes:
        path: Absolute file path
        score: Relevance score (0.0 to 1.0)
        size: File size in bytes
        modified_time: Last modification time
        reasons: List of reasons for inclusion
        extraction_mode: How to extract ("inline", "snippet", "summary")
    """
    path: Path
    score: float
    size: int
    modified_time: float
    reasons: List[str] = field(default_factory=list)
    extraction_mode: str = "inline"

    def __lt__(self, other: "FileRelevance") -> bool:
        """Compare by score for sorting."""
        return self.score < other.score


class FileContextExtractor:
    """
    Smart file context extraction with relevance scoring.

    Automatically includes relevant workspace files based on:
    - Keyword overlap with query
    - File mentions in recent conversation
    - File modification recency
    - File type and extension

    Extraction modes:
    - Inline: Full file content for small files
    - Snippet: Extract relevant functions/classes
    - Summary: Generate summary for large files
    """

    def __init__(self, workspace_root: Path, mode: str = "balanced"):
        """
        Initialize file context extractor.

        Args:
            workspace_root: Root directory of workspace
            mode: Operation mode ("cheap", "balanced", or "max_quality")

        Raises:
            ValueError: If mode is not recognized
        """
        if mode not in MODE_THRESHOLDS:
            raise ValueError(
                f"Invalid mode '{mode}'. Must be one of: {list(MODE_THRESHOLDS.keys())}"
            )
        self.workspace_root = workspace_root
        self.mode = mode
        self.thresholds = MODE_THRESHOLDS[mode]

    def scan_workspace_files(self, max_files: int = 100) -> List[Path]:
        """
        Scan workspace for relevant files.

        Args:
            max_files: Maximum number of files to return

        Returns:
            List of file paths (sorted by modification time, newest first)
        """
        files = []

        for root, dirs, filenames in os.walk(self.workspace_root):
            # Modify dirs in-place to skip certain directories
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in SKIP_DIRS]

            for filename in filenames:
                file_path = Path(root) / filename

                if should_skip_file(file_path):
                    continue

                # Check extension is relevant
                if file_path.suffix and file_path.suffix.lower() not in RELEVANT_EXTENSIONS:
                    continue

                try:
                    stat = file_path.stat()
                    if stat.st_size > 1024 * 1024:  # Skip files > 1MB
                        continue
                    files.append((file_path, stat.st_mtime))
                except (OSError, PermissionError):
                    continue

        # Sort by modification time (newest first) and limit
        files.sort(key=lambda x: x[1], reverse=True)
        return [f[0] for f in files[:max_files]]

    def score_file_relevance(
        self,
        file_path: Path,
        query: str,
        conversation_files: Set[str],
        query_keywords: Optional[Set[str]] = None
    ) -> FileRelevance:
        """
        Score file relevance to query and conversation.

        Scoring factors:
        1. Keyword overlap with query (40%)
        2. Mentioned in conversation (30%)
        3. File recency (20%)
        4. File type priority (10%)

        Args:
            file_path: Path to file
            query: Query string
            conversation_files: Set of files mentioned in recent conversation
            query_keywords: Pre-extracted query keywords (optional)

        Returns:
            FileRelevance object
        """
        score = 0.0
        reasons = []

        try:
            stat = file_path.stat()
            size = stat.st_size
            modified_time = stat.st_mtime
        except (OSError, PermissionError):
            return FileRelevance(
                path=file_path,
                score=0.0,
                size=0,
                modified_time=0.0,
                reasons=["Error accessing file"],
                extraction_mode="skip"
            )

        # Extract query keywords if not provided
        if query_keywords is None:
            query_keywords = extract_keywords(query)

        # Try to read file content for keyword matching
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(50000)  # Read first 50KB
            file_keywords = extract_keywords(content)
        except Exception:
            file_keywords = set()
            content = ""

        # 1. Keyword overlap (40%)
        if query_keywords and file_keywords:
            overlap = query_keywords.intersection(file_keywords)
            if overlap:
                keyword_score = len(overlap) / len(query_keywords)
                score += keyword_score * 0.4
                reasons.append(f"Keywords: {', '.join(list(overlap)[:3])}")

        # 2. Mentioned in conversation (30%)
        file_name = file_path.name
        file_str = str(file_path.relative_to(self.workspace_root))
        if file_str in conversation_files or file_name in conversation_files:
            score += 0.3
            reasons.append("Mentioned in conversation")

        # 3. File recency (20%) - files modified in last 24 hours get boost
        hours_old = (datetime.now().timestamp() - modified_time) / 3600
        if hours_old < 24:
            recency_score = max(0, 1.0 - (hours_old / 24))
            score += recency_score * 0.2
            if recency_score > 0.5:
                reasons.append(f"Recently modified ({hours_old:.1f}h ago)")

        # 4. File type priority (10%)
        type_priority = {
            ".py": 1.0, ".js": 0.9, ".ts": 0.9,
            ".json": 0.7, ".yaml": 0.6, ".yml": 0.6,
            ".md": 0.5, ".txt": 0.4,
        }
        ext = file_path.suffix.lower()
        if ext in type_priority:
            score += type_priority[ext] * 0.1

        # Determine extraction mode based on file size and mode
        extraction_mode = self._determine_extraction_mode(size)

        return FileRelevance(
            path=file_path,
            score=score,
            size=size,
            modified_time=modified_time,
            reasons=reasons if reasons else ["Low relevance"],
            extraction_mode=extraction_mode
        )

    def _determine_extraction_mode(self, file_size: int) -> str:
        """
        Determine how to extract file content based on size and mode.

        Args:
            file_size: File size in bytes

        Returns:
            Extraction mode: "inline", "snippet", "summary", or "skip"
        """
        if file_size <= self.thresholds["inline_max"]:
            return "inline"
        elif file_size <= self.thresholds["snippet_max"]:
            return "snippet"
        elif file_size <= self.thresholds["summarize_min"] * 2:  # Up to 2x summarize threshold
            return "summary"
        else:
            return "skip"  # Too large

    def extract_file_context(
        self,
        query: str,
        conversation_files: Optional[Set[str]] = None,
        max_files: int = 5
    ) -> List[Tuple[Path, str, List[str]]]:
        """
        Extract relevant file context for query.

        Args:
            query: Query string
            conversation_files: Set of files mentioned in conversation
            max_files: Maximum number of files to include

        Returns:
            List of (file_path, content, reasons) tuples
        """
        if conversation_files is None:
            conversation_files = set()

        # Scan workspace files
        files = self.scan_workspace_files(max_files=100)
        if not files:
            return []

        # Extract query keywords
        query_keywords = extract_keywords(query)

        # Score all files
        scored_files: List[FileRelevance] = []
        for file_path in files:
            relevance = self.score_file_relevance(
                file_path,
                query,
                conversation_files,
                query_keywords
            )
            if relevance.score > 0.1:  # Minimum relevance threshold
                scored_files.append(relevance)

        # Sort by score and take top N
        scored_files.sort(reverse=True)
        top_files = scored_files[:max_files]

        # Extract content based on extraction mode
        results = []
        for file_rel in top_files:
            content = self._extract_content(file_rel, query_keywords)
            if content:
                results.append((file_rel.path, content, file_rel.reasons))

        return results

    def _extract_content(self, file_rel: FileRelevance, query_keywords: Set[str]) -> Optional[str]:
        """
        Extract file content based on extraction mode.

        Args:
            file_rel: FileRelevance object
            query_keywords: Keywords from query

        Returns:
            Extracted content or None
        """
        try:
            with open(file_rel.path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            logger.warning(f"Failed to read {file_rel.path}: {e}")
            return None

        if file_rel.extraction_mode == "inline":
            # Return full content
            return content

        elif file_rel.extraction_mode == "snippet":
            # Extract relevant functions/classes
            return self._extract_snippets(content, file_rel.path.suffix, query_keywords)

        elif file_rel.extraction_mode == "summary":
            # Generate summary
            return self._summarize_file(content, file_rel.path)

        else:  # skip
            return None

    def _extract_snippets(self, content: str, file_ext: str, query_keywords: Set[str]) -> str:
        """
        Extract relevant code snippets based on query keywords.

        Args:
            content: File content
            file_ext: File extension
            query_keywords: Keywords from query

        Returns:
            Extracted snippets
        """
        # Extract function/class names
        symbols = extract_function_names(content, file_ext)

        # Find symbols matching query keywords
        matching_symbols = set()
        for symbol in symbols:
            symbol_lower = symbol.lower()
            if any(keyword in symbol_lower for keyword in query_keywords):
                matching_symbols.add(symbol)

        if not matching_symbols:
            # No specific matches, return beginning of file
            lines = content.split('\n')
            return '\n'.join(lines[:50]) + "\n... (truncated)"

        # Extract matched symbols with context
        snippets = []
        for symbol in matching_symbols:
            snippet = self._extract_symbol_definition(content, symbol, file_ext)
            if snippet:
                snippets.append(f"# {symbol}\n{snippet}")

        if snippets:
            return '\n\n'.join(snippets[:5])  # Max 5 snippets
        else:
            lines = content.split('\n')
            return '\n'.join(lines[:50]) + "\n... (truncated)"

    def _extract_symbol_definition(self, content: str, symbol: str, file_ext: str) -> Optional[str]:
        """
        Extract definition of a symbol (function/class) with context.

        Args:
            content: File content
            symbol: Symbol name
            file_ext: File extension

        Returns:
            Symbol definition or None
        """
        lines = content.split('\n')

        # Find line with symbol definition
        if file_ext == ".py":
            pattern = rf'^\s*(def|class|async\s+def)\s+{re.escape(symbol)}\b'
        elif file_ext in {".js", ".ts", ".jsx", ".tsx"}:
            pattern = rf'\b(function|class)\s+{re.escape(symbol)}\b'
        else:
            pattern = rf'\b{re.escape(symbol)}\b'

        for i, line in enumerate(lines):
            if re.search(pattern, line):
                # Extract up to 30 lines or until next definition
                end = min(i + 30, len(lines))
                snippet_lines = lines[i:end]
                return '\n'.join(snippet_lines)

        return None

    def _summarize_file(self, content: str, file_path: Path) -> str:
        """
        Generate summary of file content.

        Args:
            content: File content
            file_path: Path to file

        Returns:
            Summary string
        """
        lines = content.split('\n')
        total_lines = len(lines)

        # Extract first few lines (usually imports/header)
        header = '\n'.join(lines[:10])

        # Extract function/class names
        symbols = extract_function_names(content, file_path.suffix)

        summary_parts = [
            f"# File: {file_path.name}",
            f"# Lines: {total_lines}",
            f"# Size: {len(content)} bytes",
            "",
            "## Header:",
            header,
            "",
            f"## Symbols ({len(symbols)}):",
            ", ".join(sorted(symbols)[:20]) if symbols else "None found",
            "",
            "... (file content truncated for context)"
        ]

        return '\n'.join(summary_parts)


__all__ = [
    "FileRelevance",
    "FileContextExtractor",
    "should_skip_file",
    "extract_function_names",
    "MODE_THRESHOLDS",
    "RELEVANT_EXTENSIONS",
    "SKIP_EXTENSIONS",
    "SKIP_DIRS",
]
