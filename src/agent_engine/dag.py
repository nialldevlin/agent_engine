"""Directed Acyclic Graph (DAG) for workflow execution.

Provides a dedicated DAG class with adjacency structures for efficient routing
and validation of workflow graphs per AGENT_ENGINE_SPEC §2-3.
"""

from typing import Dict, List, Optional

from .exceptions import DAGValidationError
from .schemas.stage import Node, NodeRole
from .schemas.workflow import Edge, validate_workflow_graph


class DAG:
    """Directed Acyclic Graph for workflow execution.

    Implements the core routing structure for Agent Engine workflows, providing
    efficient adjacency-based lookups and comprehensive validation per
    AGENT_ENGINE_SPEC §2-3.

    The DAG maintains:
    - nodes: Dictionary mapping node_id to Node objects
    - edges: List of Edge objects forming the routing structure
    - adjacency: Efficient adjacency map for outbound edge lookups

    All nodes must be reachable from the default start node, and the default
    start node must be able to reach at least one exit node.
    """

    def __init__(self, nodes: Dict[str, Node], edges: List[Edge]):
        """Initialize DAG with nodes and edges.

        Args:
            nodes: Dictionary mapping node_id (string) to Node objects.
            edges: List of Edge objects defining the routing structure.

        Raises:
            DAGValidationError: If nodes or edges are invalid or if DAG
                               structure violates workflow invariants.
        """
        self.nodes = nodes
        self.edges = edges
        self.adjacency = self._build_adjacency()

    def _build_adjacency(self) -> Dict[str, List[Edge]]:
        """Build adjacency map: node_id -> list of outbound edges.

        Creates an efficient lookup structure for finding all outbound edges
        from any given node. This enables O(1) lookup for routing decisions.

        Returns:
            Dictionary mapping each node_id to a list of Edge objects
            that originate from that node.
        """
        adj = {node_id: [] for node_id in self.nodes}
        for edge in self.edges:
            if edge.from_node_id in adj:
                adj[edge.from_node_id].append(edge)
        return adj

    def get_node(self, node_id: str) -> Node:
        """Get node by ID.

        Args:
            node_id: The unique identifier of the node to retrieve.

        Returns:
            The Node object with the given ID.

        Raises:
            KeyError: If the node ID does not exist in the DAG.
        """
        if node_id not in self.nodes:
            raise KeyError(f"Node {node_id} not found in DAG")
        return self.nodes[node_id]

    def get_outbound_edges(self, node_id: str) -> List[Edge]:
        """Get all outbound edges from a node.

        Returns the list of edges that originate from the specified node,
        enabling efficient routing decisions and graph traversal.

        Args:
            node_id: The ID of the node to query.

        Returns:
            List of Edge objects originating from the node. Returns empty list
            if the node has no outbound edges (e.g., EXIT nodes).
        """
        return self.adjacency.get(node_id, [])

    def get_default_start_node(self) -> Node:
        """Get the default start node.

        Returns:
            The unique START node marked with default_start=True.

        Raises:
            DAGValidationError: If exactly one default start node cannot be found.
                               This indicates the DAG was not properly validated.
        """
        start_nodes = [
            node for node in self.nodes.values()
            if node.role == NodeRole.START and node.default_start
        ]
        if len(start_nodes) != 1:
            raise DAGValidationError(
                f"Expected exactly one default start node, found {len(start_nodes)}"
            )
        return start_nodes[0]

    def validate(self) -> None:
        """Validate DAG structure and constraints.

        Performs comprehensive validation of the DAG using Phase 1 validation logic.
        Checks all structural and semantic invariants per AGENT_ENGINE_SPEC §2-3:

        - DAG is acyclic
        - Exactly one default START node exists
        - At least one EXIT node exists
        - All nodes are reachable from default START
        - Default START can reach at least one EXIT
        - Kind-role constraints are satisfied (START/EXIT must be DETERMINISTIC)
        - Context field validation
        - Agent ID validation for AGENT kind nodes
        - Role-based edge count constraints

        Raises:
            DAGValidationError: If any validation check fails, with a descriptive
                               error message indicating what constraint was violated.
        """
        try:
            # Create a minimal WorkflowGraph-like object for validation
            from .schemas.workflow import WorkflowGraph

            workflow = WorkflowGraph(
                workflow_id="validation",
                nodes=list(self.nodes.values()),
                edges=self.edges
            )
            validate_workflow_graph(workflow, nodes=self.nodes)
        except ValueError as e:
            raise DAGValidationError(str(e))
        except Exception as e:
            raise DAGValidationError(f"Unexpected validation error: {str(e)}")
