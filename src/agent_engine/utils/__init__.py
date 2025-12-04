"""Utility modules for Agent Engine."""

from .token_utils import (
    estimate_tokens_rough,
    estimate_tokens_messages,
    estimate_prompt_tokens,
    estimate_tokens,
    CHARS_PER_TOKEN,
)

from .text_analysis import (
    extract_keywords,
    calculate_relevance_score,
    STOP_WORDS,
)

from .version_utils import (
    parse_version,
    compare_versions,
    is_compatible,
)

from .file_context import (
    FileRelevance,
    FileContextExtractor,
    should_skip_file,
    extract_function_names,
    MODE_THRESHOLDS,
    RELEVANT_EXTENSIONS,
    SKIP_EXTENSIONS,
    SKIP_DIRS,
)

from .filesystem_safety import (
    validate_path_traversal,
    is_binary_file,
    DEFAULT_MAX_READ_BYTES,
    DEFAULT_MAX_WRITE_BYTES,
)

from .json_io import (
    read_json_safe,
    write_json_safe,
    validate_json_structure,
)

__all__ = [
    # Token utils
    "estimate_tokens_rough",
    "estimate_tokens_messages",
    "estimate_prompt_tokens",
    "estimate_tokens",
    "CHARS_PER_TOKEN",
    # Text analysis
    "extract_keywords",
    "calculate_relevance_score",
    "STOP_WORDS",
    # Version utils
    "parse_version",
    "compare_versions",
    "is_compatible",
    # File context
    "FileRelevance",
    "FileContextExtractor",
    "should_skip_file",
    "extract_function_names",
    "MODE_THRESHOLDS",
    "RELEVANT_EXTENSIONS",
    "SKIP_EXTENSIONS",
    "SKIP_DIRS",
    # Filesystem safety utils
    "validate_path_traversal",
    "is_binary_file",
    "DEFAULT_MAX_READ_BYTES",
    "DEFAULT_MAX_WRITE_BYTES",
    # JSON I/O utils
    "read_json_safe",
    "write_json_safe",
    "validate_json_structure",
]
