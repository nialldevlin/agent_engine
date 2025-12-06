"""Workflow graph and pipeline schemas."""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import Field

from .base import SchemaBase


class Edge(SchemaBase):
    from_stage_id: str
    to_stage_id: str
    condition: Optional[str] = Field(default=None, description="Tag or expression")
    edge_id: Optional[str] = None
    edge_type: Optional[str] = None


class WorkflowGraph(SchemaBase):
    workflow_id: str
    stages: List[str] = Field(..., description="List of stage IDs")
    edges: List[Edge] = Field(default_factory=list)
    invariants: Dict[str, bool] = Field(default_factory=dict)
    start_stage_ids: List[str] = Field(default_factory=list, description="Start stage IDs for the workflow")
    end_stage_ids: List[str] = Field(default_factory=list, description="End stage IDs for the workflow")

class Pipeline(SchemaBase):
    pipeline_id: str
    name: str
    description: str
    workflow_id: str
    start_stage_ids: List[str]
    end_stage_ids: List[str]
    allowed_modes: List[str] = Field(default_factory=list)
    fallback_end_stage_ids: List[str] = Field(default_factory=list)
    metadata: Dict[str, object] = Field(default_factory=dict)


def validate_workflow_graph(graph: WorkflowGraph) -> None:
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
    for e in graph.edges:
        if e.from_stage_id not in stage_set:
            raise ValueError(f"Edge.from_stage_id references unknown stage: {e.from_stage_id}")
        if e.to_stage_id not in stage_set:
            raise ValueError(f"Edge.to_stage_id references unknown stage: {e.to_stage_id}")
        adj[e.from_stage_id].append(e.to_stage_id)
        incoming_count[e.to_stage_id] = incoming_count.get(e.to_stage_id, 0) + 1

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

    # All checks passed
    return None
