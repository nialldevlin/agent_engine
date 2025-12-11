"""Node schemas for canonical Agent Engine architecture."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import Field

from .base import SchemaBase


class NodeKind(str, Enum):
    """Node computation type - whether the node invokes an LLM or executes deterministic logic.

    Per AGENT_ENGINE_SPEC §2.2 and AGENT_ENGINE_OVERVIEW §1.2:
    - AGENT: Node invokes an LLM/agent model to generate decisions or outputs.
    - DETERMINISTIC: Node executes deterministic logic (tools, merges, routing, normalization).

    Invariants:
    - START and EXIT roles must be DETERMINISTIC.
    - All other roles may be either AGENT or DETERMINISTIC.
    - AGENT nodes must have an agent_id; DETERMINISTIC nodes may have agent_id=None.
    """

    AGENT = "agent"
    DETERMINISTIC = "deterministic"


class NodeRole(str, Enum):
    """Node routing role - position and execution semantics in the DAG.

    Per AGENT_ENGINE_SPEC §2.2 and AGENT_ENGINE_OVERVIEW §1.3:

    START: Workflow entry point; normalizes raw input into structured Task format.
    - Must be DETERMINISTIC.
    - Exactly 0 inbound edges, 1 outbound edge.
    - Multiple start nodes allowed; exactly one must have default_start=True.

    LINEAR: General-purpose Task transformation node.
    - May be AGENT or DETERMINISTIC.
    - Exactly 1 inbound edge, 1 outbound edge.

    DECISION: Selects exactly one of multiple outbound edges based on output.
    - May be AGENT or DETERMINISTIC.
    - Exactly 1 inbound edge, ≥2 outbound edges.
    - Output must identify a valid target edge or node fails.

    BRANCH: Creates parallel clones of the current Task.
    - May be AGENT or DETERMINISTIC (typically DETERMINISTIC).
    - Exactly 1 inbound edge, ≥2 outbound edges.
    - Parent Task completes when one clone reaches exit (unless merged).

    SPLIT: Creates hierarchical subtasks.
    - May be AGENT or DETERMINISTIC (typically DETERMINISTIC).
    - Exactly 1 inbound edge, ≥1 outbound edges.
    - Parent Task waits for all subtasks to complete (unless merged).

    MERGE: Reconciles multiple upstream results (clones or subtasks).
    - Must be DETERMINISTIC.
    - ≥2 inbound edges, exactly 1 outbound edge.
    - Receives structured list of successful upstream outputs.

    EXIT: Finalizes Task; returns output to user.
    - Must be DETERMINISTIC; read-only, no LLM invocation, no tool calls.
    - ≥1 inbound edges, exactly 0 outbound edges.
    - Reads Task status set by earlier stages and presents to user.
    """

    START = "start"
    LINEAR = "linear"
    DECISION = "decision"
    BRANCH = "branch"
    SPLIT = "split"
    MERGE = "merge"
    EXIT = "exit"


class Node(SchemaBase):
    """Declarative node definition – one vertex in the workflow DAG.

    Per AGENT_ENGINE_SPEC §2.2, AGENT_ENGINE_OVERVIEW §1.2, and PROJECT_INTEGRATION_SPEC §3.1:

    A Node represents a single atomic operation in a workflow: either an agent invocation or
    deterministic computation (tool execution, routing, merging results). Nodes are connected
    via edges to form a directed acyclic graph (DAG).

    Kind-Role Invariants:
    - Every node has exactly one kind (AGENT or DETERMINISTIC).
    - Every node has exactly one role (START, LINEAR, DECISION, BRANCH, SPLIT, MERGE, EXIT).
    - START and EXIT roles must be DETERMINISTIC.
    - All other roles may be AGENT or DETERMINISTIC.
    - AGENT nodes must have a non-None agent_id.
    - DETERMINISTIC nodes must not invoke LLM agents.

    Context and Memory Invariants:
    - Every node must specify exactly one of: context profile ID, "global", or "none".
    - This ensures clear, deterministic visibility of information during execution.
    - Context is assembled before node execution and is read-only.

    Tool and Permission Invariants:
    - Deterministic nodes may specify allowed tools via the tools field.
    - Tool invocation is restricted to tools listed in the node's tools field.
    - Tools must comply with configured permissions (see ToolDefinition).

    Fields:
        stage_id: Unique identifier for the node (globally unique across workflow).
        name: Human-readable name for debugging and logging.
        kind: Computation type (AGENT or DETERMINISTIC).
        role: Routing role in the DAG (START, LINEAR, DECISION, BRANCH, SPLIT, MERGE, EXIT).
        default_start: True if this is the default start node for the workflow.
                       Exactly one START node must have default_start=True.
        agent_id: Agent definition ID (required when kind=AGENT, must be None when kind=DETERMINISTIC).
        tools: List of allowed tool IDs for this node to invoke.
        inputs_schema_id: Optional schema ID for validating node inputs.
        outputs_schema_id: Optional schema ID for validating node outputs.
        continue_on_failure: If True, continue execution even if this node fails.
                            If False (default), stop on node failure.
        always_fail: For EXIT nodes only. If True, overrides task.status to FAILED
                     regardless of current status. Used for error exit nodes that
                     should always report failure.
        context: Context profile ID, or literal 'global' or 'none'.
                 Controls which memory layers are visible to this node.
        merge: Merge-specific configuration (strategy, aggregation rules, etc.).
               Only used and required when role == MERGE.
        merge_failure_mode: How merge handles failures: 'fail_on_any' (default),
                           'ignore_failures', or 'partial'.
        metadata: Additional node-specific data (e.g., retry hints, monitoring tags).
    """

    stage_id: str
    name: str
    kind: NodeKind
    role: NodeRole
    default_start: bool = Field(
        default=False,
        description="True if this is the default start node for the workflow"
    )
    agent_id: Optional[str] = Field(
        default=None,
        description="Agent definition ID; required when kind == 'agent'"
    )
    tools: List[str] = Field(
        default_factory=list,
        description="List of allowed tool IDs"
    )
    inputs_schema_id: Optional[str] = Field(
        default=None,
        description="Optional schema ID for validating node inputs"
    )
    outputs_schema_id: Optional[str] = Field(
        default=None,
        description="Optional schema ID for validating node outputs"
    )
    continue_on_failure: bool = Field(
        default=False,
        description="If True, continue execution even if this node fails"
    )
    always_fail: bool = Field(
        default=False,
        description="If True (EXIT nodes only), override task status to FAILED"
    )
    context: str = Field(
        ...,
        description="Context profile ID, or literal 'global' or 'none'"
    )
    merge: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Merge-specific configuration (strategy, aggregation rules, etc.); only used when role == 'merge'"
    )
    merge_failure_mode: Optional[str] = Field(
        default="fail_on_any",
        description="How merge handles failures: 'fail_on_any', 'ignore_failures', 'partial'"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional node-specific data"
    )
