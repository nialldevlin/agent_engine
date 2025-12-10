"""Workflow graph and edge schemas."""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import Field

from .base import SchemaBase
from .stage import Node, NodeRole


class Edge(SchemaBase):
    """A directed edge in the workflow DAG connecting two nodes.

    Per AGENT_ENGINE_SPEC §2.3, AGENT_ENGINE_OVERVIEW §2.2, and PROJECT_INTEGRATION_SPEC §3.1:

    Edges are simple directed pairs (from_node_id, to_node_id) that form the explicit routing
    structure of the DAG. Routing semantics are determined by source node role, not edge type.
    The DAG is the sole routing mechanism; no implicit routing exists.

    Routing Invariants:
    - All routing must be explicitly defined as edges in the DAG.
    - Pipelines are emergent execution traces produced when Tasks flow through the graph.
    - The condition field is used by DECISION nodes to select among multiple outbound edges.
    - Other node roles ignore the condition field.

    DAG Structural Invariants:
    - The DAG must be acyclic.
    - All nodes must be reachable from at least one START node.
    - All START nodes must be able to reach at least one EXIT node.
    - Edge counts per node role are strictly validated:
      - START: 0 inbound, 1 outbound
      - LINEAR: 1 inbound, 1 outbound
      - DECISION: 1 inbound, ≥2 outbound
      - BRANCH: 1 inbound, ≥2 outbound
      - SPLIT: 1 inbound, ≥1 outbound
      - MERGE: ≥2 inbound, 1 outbound
      - EXIT: ≥1 inbound, 0 outbound

    Fields:
        from_node_id: Source node ID (must exist in workflow).
        to_node_id: Target node ID (must exist in workflow).
        condition: Optional label/tag for DECISION routing (ignored for other roles).
        edge_id: Optional edge identifier for debugging and logging.
    """

    from_node_id: str
    to_node_id: str
    condition: Optional[str] = Field(default=None, description="Optional label/tag for decision routing")
    edge_id: Optional[str] = Field(default=None, description="Optional edge identifier")


class WorkflowGraph(SchemaBase):
    """Complete DAG defining all workflow nodes and transitions.

    Per AGENT_ENGINE_SPEC §2.1-2.3, AGENT_ENGINE_OVERVIEW §2.1-2.4, and PROJECT_INTEGRATION_SPEC §3.1:

    A WorkflowGraph is the complete specification of a project's workflow execution. It contains
    all nodes and edges that comprise the DAG. The engine executes exactly one WorkflowGraph per
    project, and that graph defines all possible execution paths.

    DAG Invariants (enforced by validate_workflow_graph):
    - Exactly one workflow DAG per project.
    - DAG must be acyclic (no cycles allowed).
    - At least one START node with role=START must exist.
    - Exactly one START node must have default_start=True (the default entry point).
    - At least one EXIT node with role=EXIT must exist.
    - All nodes must be reachable from the default START node.
    - All START nodes must be able to reach at least one EXIT node.
    - All edges must reference existing nodes.
    - Node kind-role constraints must be satisfied (START and EXIT must be DETERMINISTIC).
    - Context field validation (must be non-empty string, "global", or "none").
    - Agent ID validation (AGENT kind must have agent_id).
    - Role-based edge count constraints for all roles.

    Parallelism Invariants:
    - BRANCH nodes create clones; parent completes when one clone reaches exit (unless merged).
    - SPLIT nodes create subtasks; parent waits for all subtasks (unless merged).
    - MERGE nodes wait for all inbound tasks and must be deterministic.

    Fields:
        workflow_id: Unique workflow identifier (globally unique for the project).
        nodes: List of nodes (as Node objects or node IDs).
               Must contain at least one START and one EXIT.
        edges: Directed edges connecting nodes.
               Forms the complete routing structure of the DAG.
        invariants: Optional metadata about graph properties (for documentation/validation).
    """

    workflow_id: str
    nodes: List = Field(..., description="List of all nodes (as Node objects or node IDs)")
    edges: List[Edge] = Field(default_factory=list, description="Directed edges connecting nodes")
    invariants: Dict[str, bool] = Field(default_factory=dict, description="Optional graph invariant metadata")


# DEPRECATED: Pipeline class is not part of canonical architecture
# Keeping for reference only - DO NOT USE in active code
#
# class Pipeline(SchemaBase):
#     """A concrete traversal through the WorkflowGraph – a specific path from entry to exit.
#
#     A pipeline specifies which start and end stages are used for a particular execution mode
#     or task type. Multiple pipelines can traverse the same underlying workflow graph but use
#     different subsets of entry/exit nodes and may enforce different constraints (e.g., allowed modes).
#
#     Per AGENT_ENGINE_OVERVIEW §5.3 and AGENT_ENGINE_SPEC §3.2:
#     - A pipeline is an acyclic path or branching tree that converges and terminates.
#     - The router selects which pipeline to use for a task.
#     - Pipelines can define fallback exit nodes for error cases.
#
#     Fields:
#         pipeline_id: Unique identifier.
#         name: Human-readable name.
#         description: Description of this pipeline's purpose.
#         workflow_id: Reference to the WorkflowGraph this pipeline traverses.
#         start_stage_ids: Entry stage(s) for this pipeline.
#         end_stage_ids: Normal exit stage(s) for successful completion.
#         allowed_modes: Optional task modes (TaskMode values) allowed for this pipeline.
#         fallback_end_stage_ids: Optional fallback exit stage(s) for error cases.
#         metadata: Pipeline-specific metadata.
#     """
#
#     pipeline_id: str = Field(..., description="Unique pipeline identifier")
#     name: str = Field(..., description="Human-readable pipeline name")
#     description: str = Field(..., description="Description of pipeline purpose")
#     workflow_id: str = Field(..., description="Reference to WorkflowGraph this pipeline uses")
#     start_stage_ids: List[str] = Field(..., description="Entry stage(s)")
#     end_stage_ids: List[str] = Field(..., description="Normal exit stage(s)")
#     allowed_modes: List[str] = Field(default_factory=list, description="Optional task modes (TaskMode values) allowed")
#     fallback_end_stage_ids: List[str] = Field(default_factory=list, description="Optional fallback exit stage(s) for errors")
#     metadata: Dict[str, object] = Field(default_factory=dict, description="Pipeline-specific metadata")


def validate_workflow_graph(graph: WorkflowGraph, *, nodes: Optional[Dict[str, "Node"]] = None) -> None:
    """Validate a WorkflowGraph for canonical DAG invariants per AGENT_ENGINE_SPEC §2-3.

    This function enforces all structural, semantic, and routing invariants required for a valid
    Agent Engine workflow. It is called during engine initialization and should be called whenever
    a WorkflowGraph is loaded from configuration.

    Args:
        graph: The WorkflowGraph to validate.
        nodes: Optional dict of Node objects keyed by node ID. If provided, enables full semantic
               validation. If not provided, performs graph-level structural checks only.

    Raises:
        ValueError: On validation failure, with a clear message describing the invariant violation.

    Validation Checks (in order):

    1. Node Existence & Extraction
       - All nodes must have identifiable IDs (string, dict with 'stage_id', or object with 'stage_id' attr).
       - At least one node must exist.

    2. Kind-Role Constraints (when nodes provided)
       - START nodes must be DETERMINISTIC.
       - EXIT nodes must be DETERMINISTIC.
       - AGENT nodes must have a non-None agent_id.
       - DETERMINISTIC nodes may optionally have agent_id=None.

    3. Context Field Validation (when nodes provided)
       - All nodes must have a context field with a non-empty string, 'global', or 'none'.

    4. Edge Validation
       - All edges must reference existing nodes (from_node_id and to_node_id).
       - Invalid edge references cause immediate failure.

    5. Cycle Detection
       - Graph must be acyclic (DFS-based cycle detection).
       - Cycles are detected before start/exit checks to catch all errors.

    6. Start Node Detection & Validation (when nodes provided)
       - At least one node must have role=START.
       - Exactly one START node must have default_start=True.
       - Non-START nodes must not have default_start=True.

    7. Exit Node Detection
       - At least one node must have role=EXIT.

    8. Reachability Checks (when nodes provided)
       - All nodes must be reachable from the default START node.
       - The default START node must be able to reach at least one EXIT node.
       - Unreachable nodes and disconnected exit nodes cause failure.

    9. Role-Based Edge Count Validation (when nodes provided)
       - START: exactly 0 inbound, 1 outbound.
       - LINEAR: exactly 1 inbound, 1 outbound.
       - DECISION: exactly 1 inbound, ≥2 outbound.
       - BRANCH: exactly 1 inbound, ≥2 outbound.
       - SPLIT: exactly 1 inbound, ≥1 outbound.
       - MERGE: ≥2 inbound, exactly 1 outbound.
       - EXIT: ≥1 inbound, exactly 0 outbound.
    """
    from .stage import NodeKind

    # Extract node IDs from graph.nodes (which may contain Node objects, dicts, or strings)
    node_set = set()
    for item in graph.nodes:
        if isinstance(item, str):
            node_set.add(item)
        elif isinstance(item, dict):
            # Handle dict representation of nodes (e.g., from YAML)
            if 'stage_id' in item:
                node_set.add(item['stage_id'])
            else:
                raise ValueError(f"Invalid node entry in workflow: {item}")
        elif hasattr(item, 'stage_id'):
            node_set.add(item.stage_id)
        else:
            raise ValueError(f"Invalid node entry in workflow: {item}")
    if not node_set:
        raise ValueError("WorkflowGraph must declare at least one node")

    # Build adjacency list and incoming edge counts
    adj: Dict[str, List[str]] = {n: [] for n in node_set}
    incoming_count: Dict[str, int] = {n: 0 for n in node_set}
    node_lookup: Optional[Dict[str, Node]] = None
    if nodes is not None:
        missing = node_set - set(nodes.keys())
        if missing:
            raise ValueError(f"Workflow references undefined node metadata: {sorted(list(missing))}")
        node_lookup = nodes

    # 1. Kind-Role Constraint Validation: START and EXIT must be DETERMINISTIC
    if node_lookup:
        for node_id, node in node_lookup.items():
            if node.role == NodeRole.START and node.kind != NodeKind.DETERMINISTIC:
                raise ValueError(
                    f"Node '{node_id}' has role START but kind '{node.kind}'; "
                    "START nodes must be DETERMINISTIC"
                )
            if node.role == NodeRole.EXIT and node.kind != NodeKind.DETERMINISTIC:
                raise ValueError(
                    f"Node '{node_id}' has role EXIT but kind '{node.kind}'; "
                    "EXIT nodes must be DETERMINISTIC"
                )

    # 2. Context Field Validation
    if node_lookup:
        for node_id, node in node_lookup.items():
            if not isinstance(node.context, str) or node.context == "":
                raise ValueError(
                    f"Node '{node_id}' has invalid context: {node.context}; "
                    "context must be a non-empty string, 'global', or 'none'"
                )
            if node.context not in ("global", "none") and not node.context.strip():
                raise ValueError(
                    f"Node '{node_id}' has invalid context: {node.context}; "
                    "context must be a non-empty string, 'global', or 'none'"
                )

    # 3. Agent ID Validation: AGENT kind must have agent_id
    if node_lookup:
        for node_id, node in node_lookup.items():
            if node.kind == NodeKind.AGENT and node.agent_id is None:
                raise ValueError(
                    f"Node '{node_id}' has kind AGENT but agent_id is None; "
                    "AGENT nodes must have a non-None agent_id"
                )
            if node.kind == NodeKind.DETERMINISTIC and node.agent_id is not None:
                # This is a warning but not an error; log it but continue
                pass

    # Validate edges reference known nodes
    for e in graph.edges:
        if e.from_node_id not in node_set:
            raise ValueError(f"Edge.from_node_id references unknown node: {e.from_node_id}")
        if e.to_node_id not in node_set:
            raise ValueError(f"Edge.to_node_id references unknown node: {e.to_node_id}")
        adj[e.from_node_id].append(e.to_node_id)
        incoming_count[e.to_node_id] = incoming_count.get(e.to_node_id, 0) + 1

    # Cycle detection via DFS (run before start/end checks so cycles are detected even
    # when no node has zero incoming edges).
    visited: Dict[str, int] = {n: 0 for n in node_set}  # 0=unvisited, 1=visiting, 2=visited

    def dfs_cycle(node: str) -> None:
        if visited[node] == 1:
            raise ValueError(f"Cycle detected at node: {node}")
        if visited[node] == 2:
            return
        visited[node] = 1
        for nbr in adj.get(node, []):
            dfs_cycle(nbr)
        visited[node] = 2

    for n in node_set:
        if visited[n] == 0:
            dfs_cycle(n)

    # Determine start and exit nodes based on node roles and default_start flag
    start_node_ids = []
    exit_node_ids = []
    default_start_node_id = None

    if node_lookup:
        for node_id, node in node_lookup.items():
            if node.role == NodeRole.START:
                start_node_ids.append(node_id)
                if node.default_start:
                    if default_start_node_id is not None:
                        raise ValueError(f"Multiple nodes have default_start=True; expected exactly one")
                    default_start_node_id = node_id
            if node.role == NodeRole.EXIT:
                exit_node_ids.append(node_id)

        # 4. Default Start Validation: exactly one START with default_start=True
        if default_start_node_id is None:
            raise ValueError("WorkflowGraph must have exactly one START node with default_start == True")

        # Validate that non-START nodes don't have default_start=True
        for node_id, node in node_lookup.items():
            if node.role != NodeRole.START and node.default_start:
                raise ValueError(
                    f"Node '{node_id}' has default_start=True but role is '{node.role}'; "
                    "only START nodes can have default_start=True"
                )
    else:
        # If no node metadata provided, fall back to graph structure
        start_node_ids = [n for n, inc in incoming_count.items() if inc == 0]
        exit_node_ids = [n for n, outs in adj.items() if len(outs) == 0]

    if not start_node_ids:
        raise ValueError("WorkflowGraph must have at least one START node (role == 'start')")
    if not exit_node_ids:
        raise ValueError("WorkflowGraph must have at least one EXIT node (role == 'exit')")

    # Use the default start node for reachability checks, or the first start if no default specified
    start_for_reachability = default_start_node_id or start_node_ids[0]

    # Reachability: every node should be reachable from the default start
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

    reachable_from_start: set = set()
    dfs_reach(start_for_reachability, reachable_from_start)

    missing = node_set - reachable_from_start
    if missing:
        raise ValueError(f"Unreachable node(s) from default start '{start_for_reachability}': {sorted(list(missing))}")

    # Ensure from the default start there is a path to at least one exit
    if not any(exit_id in reachable_from_start for exit_id in exit_node_ids):
        raise ValueError(f"Default start node '{start_for_reachability}' cannot reach any exit node")

    # 5. Enhanced Role-Based Edge Count Validation
    if node_lookup:
        for node_id, node in node_lookup.items():
            inbound = incoming_count.get(node_id, 0)
            outbound = len(adj.get(node_id, []))

            if node.role == NodeRole.START:
                if inbound != 0:
                    raise ValueError(
                        f"Node '{node_id}' has role START but {inbound} inbound edge(s); "
                        "START nodes must have exactly 0 inbound edges"
                    )
                if outbound != 1:
                    raise ValueError(
                        f"Node '{node_id}' has role START but {outbound} outbound edge(s); "
                        "START nodes must have exactly 1 outbound edge"
                    )
            elif node.role == NodeRole.EXIT:
                if inbound < 1:
                    raise ValueError(
                        f"Node '{node_id}' has role EXIT but {inbound} inbound edge(s); "
                        "EXIT nodes must have at least 1 inbound edge"
                    )
                if outbound != 0:
                    raise ValueError(
                        f"Node '{node_id}' has role EXIT but {outbound} outbound edge(s); "
                        "EXIT nodes must have exactly 0 outbound edges"
                    )
            elif node.role == NodeRole.LINEAR:
                if inbound != 1:
                    raise ValueError(
                        f"Node '{node_id}' has role LINEAR but {inbound} inbound edge(s); "
                        "LINEAR nodes must have exactly 1 inbound edge"
                    )
                if outbound != 1:
                    raise ValueError(
                        f"Node '{node_id}' has role LINEAR but {outbound} outbound edge(s); "
                        "LINEAR nodes must have exactly 1 outbound edge"
                    )
            elif node.role == NodeRole.DECISION:
                if inbound != 1:
                    raise ValueError(
                        f"Node '{node_id}' has role DECISION but {inbound} inbound edge(s); "
                        "DECISION nodes must have exactly 1 inbound edge"
                    )
                if outbound < 2:
                    raise ValueError(
                        f"Node '{node_id}' has role DECISION but {outbound} outbound edge(s); "
                        "DECISION nodes must have at least 2 outbound edges"
                    )
            elif node.role == NodeRole.BRANCH:
                if inbound != 1:
                    raise ValueError(
                        f"Node '{node_id}' has role BRANCH but {inbound} inbound edge(s); "
                        "BRANCH nodes must have exactly 1 inbound edge"
                    )
                if outbound < 2:
                    raise ValueError(
                        f"Node '{node_id}' has role BRANCH but {outbound} outbound edge(s); "
                        "BRANCH nodes must have at least 2 outbound edges"
                    )
            elif node.role == NodeRole.SPLIT:
                if inbound != 1:
                    raise ValueError(
                        f"Node '{node_id}' has role SPLIT but {inbound} inbound edge(s); "
                        "SPLIT nodes must have exactly 1 inbound edge"
                    )
                if outbound < 1:
                    raise ValueError(
                        f"Node '{node_id}' has role SPLIT but {outbound} outbound edge(s); "
                        "SPLIT nodes must have at least 1 outbound edge"
                    )
            elif node.role == NodeRole.MERGE:
                if inbound < 2:
                    raise ValueError(
                        f"Node '{node_id}' has role MERGE but {inbound} inbound edge(s); "
                        "MERGE nodes must have at least 2 inbound edges"
                    )
                if outbound != 1:
                    raise ValueError(
                        f"Node '{node_id}' has role MERGE but {outbound} outbound edge(s); "
                        "MERGE nodes must have exactly 1 outbound edge"
                    )

    # All checks passed
    return None
