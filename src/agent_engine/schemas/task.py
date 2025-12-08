"""Task and TaskSpec schemas."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import Field

from .base import SchemaBase, Severity
from .errors import FailureSignature, EngineError
from .memory import ContextFingerprint


class TaskMode(str, Enum):
    """Execution mode flags for tasks – safe-mode and operational constraints.

    Per AGENT_ENGINE_SPEC §4.6 and RESEARCH Appendix A, task modes control how agents
    and tools are permitted to behave:
    - ANALYSIS_ONLY: Agents analyze and reason; tools may not mutate the workspace.
    - IMPLEMENT: Normal mode; agents and tools can both read and write.
    - REVIEW: Agents focus on inspection/feedback of existing work; no new implementation.
    - DRY_RUN: Tools are invoked in simulation mode (read-only); outputs logged but not applied.

    These modes are enforced by Tool Runtime and Agent Runtime via permission checks and
    overrides. They can be set per-task and may override manifest-level permissions.
    """

    ANALYSIS_ONLY = "analysis_only"
    IMPLEMENT = "implement"
    REVIEW = "review"
    DRY_RUN = "dry_run"


class TaskPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class TaskSpec(SchemaBase):
    task_spec_id: str = Field(..., description="Stable ID for this task spec")
    request: str = Field(..., description="Raw or normalized user ask")
    mode: TaskMode = Field(default=TaskMode.ANALYSIS_ONLY)
    priority: TaskPriority = Field(default=TaskPriority.NORMAL)
    hints: List[str] = Field(default_factory=list)
    files: List[str] = Field(default_factory=list)
    overrides: List[str] = Field(default_factory=list, description="OverrideSpec IDs")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class StageExecutionRecord(SchemaBase):
    output: Optional[Any] = Field(default=None)
    error: Optional[EngineError] = Field(default=None)
    started_at: Optional[str] = Field(default=None, description="ISO-8601 timestamp")
    completed_at: Optional[str] = Field(default=None, description="ISO-8601 timestamp")


class RoutingDecision(SchemaBase):
    stage_id: str
    decision: Optional[str] = Field(default=None)
    agent_id: Optional[str] = Field(default=None)
    timestamp: Optional[str] = Field(default=None)


class Task(SchemaBase):
    task_id: str
    spec: TaskSpec
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    pipeline_id: str
    current_stage_id: Optional[str] = Field(default=None)
    stage_results: Dict[str, StageExecutionRecord] = Field(default_factory=dict)
    routing_trace: List[RoutingDecision] = Field(default_factory=list)
    failure_signatures: List[FailureSignature] = Field(default_factory=list)
    context_fingerprint: Optional[ContextFingerprint] = Field(default=None)
    created_at: Optional[str] = Field(default=None, description="ISO-8601 timestamp")
    updated_at: Optional[str] = Field(default=None, description="ISO-8601 timestamp")

    def to_dict(self) -> Dict[str, Any]:
        """Convert Task to JSON-serializable dict.
        
        Uses Pydantic's model_dump with mode='json' to handle:
        - Nested Pydantic models (TaskSpec, StageExecutionRecord, etc.)
        - Enum conversion to strings
        - Optional fields preserved as None
        - Empty collections as {} or []
        
        Returns:
            Dict suitable for JSON serialization with no information loss.
        """
        return self.model_dump(mode='json')

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Task:
        """Deserialize Task from dictionary.
        
        Uses Pydantic's model_validate to:
        - Reconstruct nested objects
        - Validate all fields against schema
        - Raise ValidationError on schema violation
        
        Args:
            data: Dictionary matching Task schema
            
        Returns:
            Fully reconstructed Task instance
            
        Raises:
            ValidationError: If data doesn't match Task schema
        """
        return cls.model_validate(data)
