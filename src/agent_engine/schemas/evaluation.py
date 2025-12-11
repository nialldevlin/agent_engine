"""Evaluation schema definitions for Phase 12 Evaluation & Regression System."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum


class AssertionType(str, Enum):
    """Types of assertions for evaluation results."""
    EQUALS = "equals"  # Output equals expected
    CONTAINS = "contains"  # Output contains expected substring/value
    SCHEMA_VALID = "schema_valid"  # Output validates against schema
    STATUS = "status"  # Task status equals expected (success/failure/partial)
    CUSTOM = "custom"  # Custom Python assertion function


@dataclass
class Assertion:
    """Single assertion to evaluate."""
    type: AssertionType
    expected: Any = None  # Expected value (for equals, contains, status)
    field_path: Optional[str] = None  # Dot-separated path for nested fields (e.g., "result.count")
    custom_function: Optional[str] = None  # Module path for custom assertions (e.g., "myproject.assertions.check_valid")
    message: str = ""  # Custom failure message


@dataclass
class EvaluationCase:
    """Single evaluation test case."""
    id: str  # Unique identifier for this evaluation
    description: str  # Human-readable description
    input: Any  # Input payload to pass to Engine.run()
    start_node_id: Optional[str] = None  # Optional start node override
    assertions: List[Assertion] = field(default_factory=list)  # Assertions to check
    tags: List[str] = field(default_factory=list)  # Tags for grouping/filtering (e.g., ["regression", "critical"])
    enabled: bool = True  # Whether this evaluation is enabled


@dataclass
class EvaluationSuite:
    """Collection of evaluation cases."""
    name: str
    description: str = ""
    cases: List[EvaluationCase] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)  # Suite-level tags


class EvaluationStatus(str, Enum):
    """Result status for an evaluation run."""
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"  # Evaluation couldn't run due to error


@dataclass
class AssertionResult:
    """Result of a single assertion."""
    assertion: Assertion
    status: EvaluationStatus
    actual_value: Any = None  # Actual value that was tested
    error_message: str = ""  # Error message if failed


@dataclass
class EvaluationResult:
    """Result of running a single evaluation case."""
    case_id: str
    case_description: str
    status: EvaluationStatus
    task_id: str = ""  # Task ID that was executed
    task_status: str = ""  # Task final status
    task_output: Any = None  # Task final output
    assertion_results: List[AssertionResult] = field(default_factory=list)
    execution_time_ms: float = 0.0  # Time taken to execute
    error_message: str = ""  # Error message if status == ERROR
    timestamp: str = ""  # ISO-8601 timestamp
