"""Stage schemas."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional

from pydantic import Field

from .base import SchemaBase


class StageType(str, Enum):
    """Execution roles for workflow stages.

    Each stage type defines the primary *execution role* that the stage plays in a workflow.
    Stages can be connected via edges with different semantics (normal, conditional, error, fallback).

    Types (per AGENT_ENGINE_OVERVIEW §5.2 and AGENT_ENGINE_SPEC §3.2):
    - AGENT: standard LLM agent stage; calls an agent model, enforces JSON output schema.
    - TOOL: deterministic tool invocation; executes a tool with validated inputs, records outputs.
    - DECISION: branching node whose outputs select among multiple outgoing edges (conditions).
    - MERGE: joins multiple inbound paths into one (gathers results from parallel branches).
    - FEEDBACK: specialized agent stage for inspection/review; inputs prior stage outputs.
    - LINEAR: generic "transform" stage; passes context forward with minimal logic.

    Note: A stage's *execution role* (type) is independent of its *routing role* (defined by edges).
    For example, a stage can be an AGENT (execution role) and also a decision point (routing role,
    via multiple outgoing conditional edges).
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
    """Declarative stage definition – one node in the workflow DAG.

    A stage represents a single operation in a workflow: either an agent call, tool execution,
    decision branching, or merge operation. Stages are connected via edges to form a directed
    acyclic graph (DAG). Each stage must declare its execution role (type), and optionally
    reference an agent or tool depending on that role.

    Invariants:
    - AGENT, FEEDBACK, DECISION stages must have agent_id.
    - TOOL stages must have tool_id.
    - MERGE stages must have exactly one outbound edge (unless terminal).
    - DECISION stages must have at least two outbound conditional edges.
    - Stages may not have cycles (enforced by WorkflowGraph validator).

    Fields:
        stage_id: Unique identifier for the stage.
        name: Human-readable name.
        type: Execution role (per StageType).
        entrypoint: True if the stage can start a workflow.
        terminal: True if no outbound edges should follow (terminal node).
        agent_id: Agent definition to invoke (AGENT, FEEDBACK, DECISION types).
        tool_id: Tool definition to execute (TOOL type).
        inputs_schema_id: Optional schema for validating stage inputs.
        outputs_schema_id: Optional schema for validating stage outputs.
        on_error: Error handling policy (fail, retry, skip, fallback).
        metadata: Additional stage-specific data.
    """

    stage_id: str
    name: str
    type: StageType
    entrypoint: bool = Field(default=False, description="Whether the stage can start a workflow")
    terminal: bool = Field(default=False, description="True if no outbound edges should follow")
    agent_id: Optional[str] = Field(default=None, description="Agent referenced by AGENT/FEEDBACK/DECISION stages")
    tool_id: Optional[str] = Field(default=None, description="Tool referenced by TOOL stages")
    inputs_schema_id: Optional[str] = Field(default=None, description="Optional schema ID for validating stage inputs")
    outputs_schema_id: Optional[str] = Field(default=None, description="Optional schema ID for validating stage outputs")
    on_error: Dict[str, Any] = Field(
        default_factory=lambda: {
            "policy": OnErrorPolicy.FAIL.value,
            "max_retries": None,
            "fallback_stage_id": None,
        },
        description="Error handling policy: {policy, max_retries, fallback_stage_id}",
    )
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Stage-specific metadata")
