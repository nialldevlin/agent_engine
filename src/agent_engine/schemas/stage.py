"""Stage schemas."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional

from pydantic import Field

from .base import SchemaBase


class StageType(str, Enum):
    """Execution roles for workflow stages.

    These names align with the canonical plan/spec:
    - AGENT: standard LLM agent stage.
    - TOOL: deterministic tool invocation.
    - DECISION: branching node whose outputs select edges.
    - MERGE: joins multiple inbound paths.
    - FEEDBACK: specialized agent stage that inspects prior work.
    - LINEAR: generic “transform” stage that simply passes context forward.
    """

    AGENT = "agent"
    TOOL = "tool"
    DECISION = "decision"
    MERGE = "merge"
    FEEDBACK = "feedback"
    LINEAR = "linear"


class OnErrorPolicy(str, Enum):
    """Basic on-error directives; richer policies handled via router overrides."""

    FAIL = "fail"
    RETRY = "retry"
    SKIP = "skip"
    FALLBACK_STAGE = "fallback_stage"

class Stage(SchemaBase):
    """Declarative stage definition referencing either an agent or a tool."""

    stage_id: str
    name: str
    type: StageType
    entrypoint: bool = Field(default=False, description="Whether the stage can start a workflow")
    terminal: bool = Field(default=False, description="True if no outbound edges should follow")
    agent_id: Optional[str] = Field(default=None, description="Agent referenced by AGENT/FEEDBACK/DECISION stages")
    tool_id: Optional[str] = Field(default=None, description="Tool referenced by TOOL stages")
    inputs_schema_id: Optional[str] = Field(default=None)
    outputs_schema_id: Optional[str] = Field(default=None)
    on_error: Dict[str, Any] = Field(
        default_factory=lambda: {
            "policy": OnErrorPolicy.FAIL.value,
            "max_retries": None,
            "fallback_stage_id": None,
        }
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)
