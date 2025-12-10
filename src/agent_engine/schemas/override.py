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
