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


class TaskLifecycle(str, Enum):
    """Task lifecycle stage – where a Task is in its execution lifetime.

    Per AGENT_ENGINE_SPEC §2.1 and AGENT_ENGINE_OVERVIEW §1.1:

    TaskLifecycle is orthogonal to UniversalStatus. Lifecycle tracks the phase of execution,
    while status tracks the outcome or current condition. A Task may be ACTIVE and IN_PROGRESS,
    or ACTIVE and COMPLETED (finished a node but not yet exited), or CONCLUDED and COMPLETED
    (reached exit node successfully).

    Lifecycle Values:
    - QUEUED: Task created but not yet started by the engine.
    - ACTIVE: Task is currently being executed (traversing the DAG).
    - SUSPENDED: Task execution paused (e.g., awaiting user input, resource constraints).
    - CONCLUDED: Task execution completed (reached exit node, either success or failure).
    - ARCHIVED: Task moved to cold storage or historical records.
    """
    QUEUED = "queued"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CONCLUDED = "concluded"
    ARCHIVED = "archived"


class UniversalStatus(str, Enum):
    """Universal status model – outcome or state of Tasks, nodes, and tools.

    Per AGENT_ENGINE_SPEC §3.4 and AGENT_ENGINE_OVERVIEW §3.4:

    All components (nodes, tools, clones, subtasks, Tasks) use a standardized, universal
    status model. This ensures consistent, predictable status propagation throughout execution.

    Status Invariants:
    - All entities use exactly one status value from this enum.
    - Task status must be set *before* reaching an exit node.
    - Exit nodes do not determine correctness; they read the pre-set status and present it.
    - Status propagates upward: tool status → node status → task status.
    - Merge nodes may ignore or consider failure metadata per configuration.

    Status Values:
    - PENDING: Waiting to start or continue execution.
    - IN_PROGRESS: Currently executing (actively being processed).
    - COMPLETED: Finished successfully (all work done, no errors).
    - FAILED: Finished with unrecoverable error.
    - CANCELLED: Explicitly halted before normal completion.
    - BLOCKED: Cannot proceed due to unmet dependency or resource constraint.
    """
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"


# Backwards compatibility alias
TaskStatus = UniversalStatus


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
    """Task execution record – fundamental unit of work in Agent Engine.

    Per AGENT_ENGINE_SPEC §2.1, AGENT_ENGINE_OVERVIEW §1.1, and PROJECT_INTEGRATION_SPEC §1:

    A Task represents a concrete unit of work submitted by a user, agent, or system. Every user
    request becomes a Task, which flows through the workflow DAG until reaching an exit node.
    Tasks retain complete execution history and serve as the authoritative source of truth for
    all data produced during the workflow.

    Task State Dimensions (Orthogonal):
    1. Lifecycle (where in execution): QUEUED, ACTIVE, SUSPENDED, CONCLUDED, ARCHIVED
    2. Status (outcome/condition): PENDING, IN_PROGRESS, COMPLETED, FAILED, CANCELLED, BLOCKED

    Task Lineage & Spawning:
    - Tasks may spawn clones via BRANCH nodes (parallel copies of the same Task).
    - Tasks may spawn subtasks via SPLIT nodes (hierarchical child tasks).
    - All clones and subtasks retain parent_task_id for lineage tracking.
    - Parent completion follows strict rules:
      - For clones: parent completes when one clone succeeds (unless merged).
      - For subtasks: parent completes when all subtasks succeed (unless merged).

    Memory Invariants:
    - Every Task must specify three memory references (task, project, global).
    - These connect the Task to its operational context across memory layers.
    - The Context Assembler uses these references to build read-only context for each node.

    Execution History:
    - stage_results: Dict of stage_id → StageExecutionRecord (every node execution).
    - routing_trace: List of routing decisions (one entry per node execution).
    - failure_signatures: List of failures (schema mismatches, tool errors, etc.).
    - context_fingerprint: Metadata about context assembled at start.

    Fields:
        task_id: Unique task identifier (globally unique).
        spec: TaskSpec containing the normalized request and configuration.
        lifecycle: Current phase (QUEUED, ACTIVE, SUSPENDED, CONCLUDED, ARCHIVED).
        status: Current outcome (PENDING, IN_PROGRESS, COMPLETED, FAILED, CANCELLED, BLOCKED).
        current_stage_id: Most recently executed node ID (optional).
        current_output: Output from most recent node (may be None).
        stage_results: Dict mapping stage_id → StageExecutionRecord (execution history).
        routing_trace: List of RoutingDecision objects (one per node execution).
        failure_signatures: List of FailureSignature objects (all errors encountered).
        context_fingerprint: Metadata about initial context and task complexity.
        parent_task_id: ID of parent Task (if this is a clone or subtask).
        lineage_type: Relationship type to parent (e.g., "clone", "subtask", "retry").
        lineage_metadata: Additional lineage context (e.g., which branch was taken).
        task_memory_ref: Reference to task-level memory store (per PROJECT_INTEGRATION_SPEC §3.4).
        project_memory_ref: Reference to project-level memory store.
        global_memory_ref: Reference to global-level memory store.
        created_at: ISO-8601 timestamp of Task creation.
        updated_at: ISO-8601 timestamp of last update.
    """
    task_id: str
    spec: TaskSpec
    lifecycle: TaskLifecycle = Field(default=TaskLifecycle.QUEUED)
    status: UniversalStatus = Field(default=UniversalStatus.PENDING)
    current_stage_id: Optional[str] = Field(default=None)
    current_output: Optional[Any] = Field(default=None, description="Latest output from current or last stage")
    stage_results: Dict[str, StageExecutionRecord] = Field(default_factory=dict)
    routing_trace: List[RoutingDecision] = Field(default_factory=list)
    failure_signatures: List[FailureSignature] = Field(default_factory=list)
    context_fingerprint: Optional[ContextFingerprint] = Field(default=None)
    parent_task_id: Optional[str] = Field(default=None, description="ID of parent task if this is a subtask")
    lineage_type: Optional[str] = Field(default=None, description="Relationship type to parent (e.g., 'decomposed', 'retry', 'dependent')")
    lineage_metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional lineage context")
    task_memory_ref: str = Field(..., description="Reference to task-level memory store")
    project_memory_ref: str = Field(..., description="Reference to project-level memory store")
    global_memory_ref: str = Field(..., description="Reference to global-level memory store")
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
