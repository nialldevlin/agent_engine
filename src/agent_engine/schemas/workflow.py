"""Workflow graph and pipeline schemas."""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from pydantic import Field

from .base import SchemaBase
from .stage import Stage, StageType


class EdgeType(str, Enum):
    """Edge semantics – how transitions are selected in the workflow DAG.

    Per AGENT_ENGINE_OVERVIEW §5.1 and AGENT_ENGINE_SPEC §3.2:
    - NORMAL: Standard transition; always taken unless overridden.
    - CONDITIONAL: Branch from a decision stage; taken if condition is met.
    - ERROR: Fallback edge taken when a stage fails (alternative to on_error policy).
    - FALLBACK: Alternate edge for degraded/error modes (explicit fallback path).

    Invariants:
    - CONDITIONAL edges must originate from DECISION-type stages only.
    - CONDITIONAL edges must have a non-null condition field.
    - ERROR and FALLBACK edges are optional; stages can fail without them.
    """

    NORMAL = "normal"
    CONDITIONAL = "conditional"
    ERROR = "error"
    FALLBACK = "fallback"


class Edge(SchemaBase):
    """A directed edge in the workflow DAG – one transition from one stage to another.

    Edges define the possible execution paths through a workflow. The edge type and condition
    determine when this transition is taken. Multiple outgoing edges from a stage enable
    branching; multiple inbound edges to a stage enable merging.

    Fields:
        from_stage_id: Source stage ID.
        to_stage_id: Target stage ID.
        condition: Tag or expression for conditional routing (used by CONDITIONAL edges).
        edge_id: Optional edge identifier.
        edge_type: Edge semantics (per EdgeType).
    """

    from_stage_id: str
    to_stage_id: str
    condition: Optional[str] = Field(default=None, description="Tag or expression for decision routing (CONDITIONAL edges only)")
    edge_id: Optional[str] = Field(default=None, description="Optional edge identifier")
    edge_type: EdgeType = Field(default=EdgeType.NORMAL, description="Routing semantics (per EdgeType)")


class WorkflowGraph(SchemaBase):
    """A complete directed acyclic graph (DAG) describing all possible workflow paths.

    The workflow graph is the blueprint for task execution. It defines all stages and the
    transitions between them. A valid workflow must be acyclic, have at least one entry and
    exit node, and satisfy all stage/edge constraints (per Stage and Edge docstrings).

    The workflow graph itself does not prescribe which entry/exit nodes are used in any given
    execution; that is determined by Pipeline definitions, which specify specific start and
    end nodes for concrete workflows.

    Per AGENT_ENGINE_OVERVIEW §5 and AGENT_ENGINE_SPEC §3.2:
    - Stages can be connected via normal, conditional, error, or fallback edges.
    - Decision stages branch to multiple stages; merge stages join multiple branches.
    - Every valid execution path moves forward and eventually terminates (no cycles).

    Fields:
        workflow_id: Unique identifier.
        stages: List of all stage IDs in the graph.
        edges: List of directed edges connecting stages.
        invariants: Optional metadata about graph properties.
        start_stage_ids: Optional explicit entry point(s); if empty, inferred as nodes with no inbound edges.
        end_stage_ids: Optional explicit exit point(s); if empty, inferred as nodes with no outbound edges.
    """

    workflow_id: str
    stages: List[str] = Field(..., description="List of all stage IDs in the graph")
    edges: List[Edge] = Field(default_factory=list, description="Directed edges connecting stages")
    invariants: Dict[str, bool] = Field(default_factory=dict, description="Optional graph invariant metadata")
    start_stage_ids: List[str] = Field(default_factory=list, description="Explicit entry point stage IDs (optional; inferred if empty)")
    end_stage_ids: List[str] = Field(default_factory=list, description="Explicit exit point stage IDs (optional; inferred if empty)")


class Pipeline(SchemaBase):
    """A concrete traversal through the WorkflowGraph – a specific path from entry to exit.

    A pipeline specifies which start and end stages are used for a particular execution mode
    or task type. Multiple pipelines can traverse the same underlying workflow graph but use
    different subsets of entry/exit nodes and may enforce different constraints (e.g., allowed modes).

    Per AGENT_ENGINE_OVERVIEW §5.3 and AGENT_ENGINE_SPEC §3.2:
    - A pipeline is an acyclic path or branching tree that converges and terminates.
    - The router selects which pipeline to use for a task.
    - Pipelines can define fallback exit nodes for error cases.

    Fields:
        pipeline_id: Unique identifier.
        name: Human-readable name.
        description: Description of this pipeline's purpose.
        workflow_id: Reference to the WorkflowGraph this pipeline traverses.
        start_stage_ids: Entry stage(s) for this pipeline.
        end_stage_ids: Normal exit stage(s) for successful completion.
        allowed_modes: Optional task modes (TaskMode values) allowed for this pipeline.
        fallback_end_stage_ids: Optional fallback exit stage(s) for error cases.
        metadata: Pipeline-specific metadata.
    """

    pipeline_id: str = Field(..., description="Unique pipeline identifier")
    name: str = Field(..., description="Human-readable pipeline name")
    description: str = Field(..., description="Description of pipeline purpose")
    workflow_id: str = Field(..., description="Reference to WorkflowGraph this pipeline uses")
    start_stage_ids: List[str] = Field(..., description="Entry stage(s)")
    end_stage_ids: List[str] = Field(..., description="Normal exit stage(s)")
    allowed_modes: List[str] = Field(default_factory=list, description="Optional task modes (TaskMode values) allowed")
    fallback_end_stage_ids: List[str] = Field(default_factory=list, description="Optional fallback exit stage(s) for errors")
    metadata: Dict[str, object] = Field(default_factory=dict, description="Pipeline-specific metadata")


def validate_workflow_graph(graph: WorkflowGraph, *, stages: Optional[Dict[str, "Stage"]] = None) -> None:
    """Validate a WorkflowGraph for basic DAG invariants.

    Raises ValueError with a clear message on validation failure.
    Checks performed:
    - all edges reference existing stages
    - graph contains at least one entry (start) and one terminal (end) stage
    - graph is acyclic
    - every stage is reachable from at least one start and can reach at least one end
    """
    # Basic presence checks
    stage_set = set(graph.stages)
    if not stage_set:
        raise ValueError("WorkflowGraph must declare at least one stage")

    # Validate edges reference known stages
    adj: Dict[str, List[str]] = {s: [] for s in graph.stages}
    incoming_count: Dict[str, int] = {s: 0 for s in graph.stages}
    stage_lookup: Optional[Dict[str, Stage]] = None
    if stages is not None:
        missing = stage_set - set(stages.keys())
        if missing:
            raise ValueError(f"Workflow references undefined stage metadata: {sorted(list(missing))}")
        stage_lookup = {stage_id: stages[stage_id] for stage_id in graph.stages}
    for e in graph.edges:
        if e.from_stage_id not in stage_set:
            raise ValueError(f"Edge.from_stage_id references unknown stage: {e.from_stage_id}")
        if e.to_stage_id not in stage_set:
            raise ValueError(f"Edge.to_stage_id references unknown stage: {e.to_stage_id}")
        adj[e.from_stage_id].append(e.to_stage_id)
        incoming_count[e.to_stage_id] = incoming_count.get(e.to_stage_id, 0) + 1
        if stage_lookup and e.edge_type == EdgeType.CONDITIONAL:
            from_stage = stage_lookup.get(e.from_stage_id)
            if from_stage and from_stage.type != StageType.DECISION:
                raise ValueError(
                    f"Conditional edge {e.from_stage_id}->{e.to_stage_id} must originate from a decision stage"
                )

    # Cycle detection via DFS (run before start/end checks so cycles are detected even
    # when no node has zero incoming edges).
    visited: Dict[str, int] = {s: 0 for s in graph.stages}  # 0=unvisited, 1=visiting, 2=visited

    def dfs_cycle(node: str) -> None:
        if visited[node] == 1:
            raise ValueError(f"Cycle detected at stage: {node}")
        if visited[node] == 2:
            return
        visited[node] = 1
        for nbr in adj.get(node, []):
            dfs_cycle(nbr)
        visited[node] = 2

    for s in graph.stages:
        if visited[s] == 0:
            dfs_cycle(s)

    # Determine start and end nodes
    start_ids = graph.start_stage_ids or [s for s, inc in incoming_count.items() if inc == 0]
    end_ids = graph.end_stage_ids or [s for s, outs in adj.items() if len(outs) == 0]

    if not start_ids:
        raise ValueError("WorkflowGraph must have at least one start stage (start_stage_ids or a node with no incoming edges)")
    if not end_ids:
        raise ValueError("WorkflowGraph must have at least one end stage (end_stage_ids or a node with no outgoing edges)")

    # Reachability: every stage should be reachable from some start
    def dfs_reach(start: str, seen: set) -> None:
        stack = [start]
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            for nb in adj.get(n, []):
                if nb not in seen:
                    stack.append(nb)

    reachable_from_starts: set = set()
    for s in start_ids:
        if s not in stage_set:
            raise ValueError(f"start_stage_id references unknown stage: {s}")
        dfs_reach(s, reachable_from_starts)

    missing = stage_set - reachable_from_starts
    if missing:
        raise ValueError(f"Unreachable stage(s) from any start: {sorted(list(missing))}")

    # Ensure from each start there is a path to at least one end
    # Precompute reachable sets to check that at least one end is reachable
    for s in start_ids:
        seen = set()
        dfs_reach(s, seen)
        if not any(end in seen for end in end_ids):
            raise ValueError(f"Start stage '{s}' cannot reach any terminal stage: {end_ids}")

    if stage_lookup:
        for stage_id, stage in stage_lookup.items():
            inbound = incoming_count.get(stage_id, 0)
            outbound = len(adj.get(stage_id, []))
            if stage.type == StageType.MERGE:
                if inbound < 2:
                    raise ValueError(f"Merge stage '{stage_id}' must have at least two inbound edges")
                if not stage.terminal and outbound != 1:
                    raise ValueError(f"Merge stage '{stage_id}' must have exactly one outbound edge unless terminal")
            if stage.type == StageType.DECISION and outbound < 2:
                raise ValueError(f"Decision stage '{stage_id}' must have at least two outgoing edges")

    # All checks passed
    return None
