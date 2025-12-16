"""Override schemas."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional

from pydantic import Field

from .base import SchemaBase


class OverrideKind(str, Enum):
    """Categories of task overrides – high-level control knobs for task execution.

    Per AGENT_ENGINE_OVERVIEW §6 (Routing) and RESEARCH Appendix A (Security):
    - MEMORY: Control what memory is retrieved and how (context profiles, compression).
    - ROUTING: Override DAG routing or fallback edge choices.
    - SAFETY: Apply safe-mode flags (analysis_only, dry_run) or permission restrictions.
    - VERBOSITY: Control logging/telemetry verbosity.
    - MODE: Set or restrict task mode (TaskMode values).

    Overrides are applied deterministically by the router and recorded on the Task
    for auditability. They can be scoped to task, project, or global levels.
    """

    MEMORY = "memory"
    ROUTING = "routing"
    SAFETY = "safety"
    VERBOSITY = "verbosity"
    MODE = "mode"


class OverrideScope(str, Enum):
    """Scope at which an override applies.

    - TASK: Applies to a single task (highest priority).
    - PROJECT: Applies to all tasks in a project (medium priority).
    - GLOBAL: Applies to all tasks across all projects (lowest priority).

    Task-scoped overrides take precedence over project and global overrides.
    """

    TASK = "task"
    PROJECT = "project"
    GLOBAL = "global"


class OverrideSeverity(str, Enum):
    """How strictly an override is enforced.

    - HINT: Suggestion; router/agent may ignore if conflicting.
    - ENFORCE: Mandatory; must be applied or fail the task.
    """

    HINT = "hint"
    ENFORCE = "enforce"


class OverrideSpec(SchemaBase):
    """A task override – deterministic control knob for task execution.

    Overrides allow applications to temporarily modify task behavior without changing
    manifests. Examples: enforce analysis-only mode, control DAG routing decisions,
    reduce memory context, apply safe-mode flags.

    Per AGENT_ENGINE_SPEC §4.6 and RESEARCH Appendix A, overrides are applied by the
    router before execution and recorded on the Task for auditability.

    Fields:
        override_id: Unique override identifier.
        kind: Category of override (memory, routing, safety, verbosity, mode).
        scope: Scope of application (task, project, global).
        target: Optional target (e.g., stage_id, agent_id, tool_id). If None, applies broadly.
        severity: HINT or ENFORCE.
        payload: Override-specific configuration. See examples below.
        metadata: Optional additional data.

    Payload examples (depends on kind):
    - SAFETY with "analysis_only": {"mode": "analysis_only"}
    - SAFETY with "dry_run": {"mode": "dry_run"}
    - ROUTING with "condition": {"condition": "left_branch"}
    - MEMORY with compression: {"max_tokens": 2000, "compression": "aggressive"}
    - MODE with restriction: {"allowed_modes": ["analysis_only"]}
    """

    override_id: str = Field(..., description="Unique override identifier")
    kind: OverrideKind = Field(..., description="Category of override (per OverrideKind)")
    scope: OverrideScope = Field(..., description="Scope: task, project, or global")
    target: Optional[str] = Field(default=None, description="Optional target (e.g., stage_id, agent_id)")
    severity: OverrideSeverity = Field(default=OverrideSeverity.HINT, description="HINT or ENFORCE")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Override-specific payload (kind-dependent)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Optional metadata")


def _now_iso() -> str:
    """Return current UTC time in ISO format."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


class ParameterOverrideKind(str, Enum):
    """Kind of parameter override."""

    LLM_CONFIG = "llm_config"  # Temperature, max_tokens, model, etc.
    TOOL_CONFIG = "tool_config"  # Tool enabled/disabled, timeout, permissions
    EXECUTION_CONFIG = "execution"  # Node timeout, retry policy, etc.


class ParameterOverride(SchemaBase):
    """Override for LLM, tool, and execution parameters at runtime.

    Scope format:
    - "agent/{agent_id}" - applies to agent
    - "tool/{tool_id}" - applies to tool
    - "node/{node_id}" - applies to node
    - "global" - applies globally
    """

    kind: ParameterOverrideKind = Field(..., description="Kind of parameter override")
    scope: str = Field(..., description='Scope: "agent/{id}", "tool/{id}", "node/{id}", or "global"')
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="Parameter overrides (e.g., {temperature: 0.3, max_tokens: 500})"
    )
    severity: OverrideSeverity = Field(default=OverrideSeverity.HINT, description="HINT (warn if invalid) or ENFORCE (fail)")
    reason: Optional[str] = Field(default=None, description="Why this override exists")
    created_at: str = Field(default_factory=_now_iso, description="ISO timestamp of creation")


class ParameterOverrideStore:
    """Runtime storage and retrieval of parameter overrides.

    Supports three scopes with priority: TASK > PROJECT > GLOBAL
    """

    def __init__(self) -> None:
        """Initialize empty override stores."""
        self.global_overrides: Dict[str, ParameterOverride] = {}
        self.project_overrides: Dict[str, Dict[str, ParameterOverride]] = {}  # project_id -> overrides
        self.task_overrides: Dict[str, Dict[str, ParameterOverride]] = {}  # task_id -> overrides

    def add_override(
        self,
        override: ParameterOverride,
        scope: str = "global",
        project_id: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> None:
        """Add override to appropriate scope.

        Args:
            override: The parameter override to add.
            scope: Storage scope ("global", "project", or "task").
            project_id: Project ID if scope is "project" or "task".
            task_id: Task ID if scope is "task".
        """
        key = f"{override.kind}:{override.scope}"

        if scope == "global":
            self.global_overrides[key] = override
        elif scope == "project" and project_id:
            if project_id not in self.project_overrides:
                self.project_overrides[project_id] = {}
            self.project_overrides[project_id][key] = override
        elif scope == "task" and task_id:
            if task_id not in self.task_overrides:
                self.task_overrides[task_id] = {}
            self.task_overrides[task_id][key] = override

    def get_overrides(
        self,
        override_kind: ParameterOverrideKind,
        target_scope: str,
        task_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> list[ParameterOverride]:
        """Get overrides for a target, respecting priority (TASK > PROJECT > GLOBAL).

        Args:
            override_kind: The kind of override to retrieve.
            target_scope: The target scope to match (e.g., "agent/analyzer", "tool/write_file").
            task_id: Task ID to check for task-scoped overrides.
            project_id: Project ID to check for project-scoped overrides.

        Returns:
            List of matching ParameterOverride objects, in priority order.
        """
        key = f"{override_kind}:{target_scope}"
        results: list[ParameterOverride] = []

        # Check task-scoped overrides first (highest priority)
        if task_id and task_id in self.task_overrides:
            if key in self.task_overrides[task_id]:
                results.append(self.task_overrides[task_id][key])
                return results

        # Check project-scoped overrides (medium priority)
        if project_id and project_id in self.project_overrides:
            if key in self.project_overrides[project_id]:
                results.append(self.project_overrides[project_id][key])
                return results

        # Check global overrides (lowest priority)
        if key in self.global_overrides:
            results.append(self.global_overrides[key])

        return results

    def clear_task_overrides(self, task_id: str) -> None:
        """Clear all overrides for a task (called when task completes).

        Args:
            task_id: Task ID whose overrides should be cleared.
        """
        if task_id in self.task_overrides:
            del self.task_overrides[task_id]
