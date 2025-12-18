"""Directed Acyclic Graph (DAG) for workflow execution.

Provides a dedicated DAG class with adjacency structures for efficient routing
and validation of workflow graphs per AGENT_ENGINE_SPEC §2-3.
"""

from typing import Dict, List, Optional, Iterator

from .exceptions import DAGValidationError
from .schemas.stage import Node, NodeRole
from .schemas.workflow import Edge, validate_workflow_graph


class NodeStore(dict):
    """Dictionary-like container that iterates over Node values.

    Preserves key-based lookups for internal runtime use while allowing
    external iteration (e.g., tests) to yield Node objects directly.
    """

    def __iter__(self) -> Iterator[Node]:
        return iter(self.values())


class DAG:
    """Directed Acyclic Graph for workflow execution.

    Implements the core routing structure for Agent Engine workflows, providing
    efficient adjacency-based lookups and comprehensive validation per
    AGENT_ENGINE_SPEC §2-3.

    The DAG maintains:
    - nodes: Dictionary mapping node_id to Node objects
    - edges: List of Edge objects forming the routing structure
    - adjacency: Efficient adjacency map for outbound edge lookups
    - reverse_adjacency: Efficient reverse adjacency map for inbound edge lookups

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
        # Preserve map for internal lookups, while exposing iterable NodeStore
        self.nodes = NodeStore(nodes)
        self.edges = edges
        self.adjacency = self._build_adjacency()
        self.reverse_adjacency = self._build_reverse_adjacency()

    def _build_adjacency(self) -> Dict[str, List[Edge]]:
        """Build adjacency map: node_id -> list of outbound edges.

        Creates an efficient lookup structure for finding all outbound edges
        from any given node. This enables O(1) lookup for routing decisions.

        Returns:
            Dictionary mapping each node_id to a list of Edge objects
            that originate from that node.
        """
        adj = {node_id: [] for node_id in self.nodes.keys()}
        for edge in self.edges:
            if edge.from_node_id in adj:
                adj[edge.from_node_id].append(edge)
        return adj

    def _build_reverse_adjacency(self) -> Dict[str, List[Edge]]:
        """Build reverse adjacency map: node_id -> list of inbound edges.

        Creates an efficient lookup structure for finding all inbound edges
        to any given node. This is essential for merge node coordination,
        allowing the router to determine which upstream tasks must complete
        before a merge can execute.

        Returns:
            Dictionary mapping each node_id to a list of Edge objects
            that terminate at that node.
        """
        rev_adj = {node_id: [] for node_id in self.nodes.keys()}
        for edge in self.edges:
            if edge.to_node_id in rev_adj:
                rev_adj[edge.to_node_id].append(edge)
        return rev_adj

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

    def get_inbound_edges(self, node_id: str) -> List[Edge]:
        """Get all inbound edges to a node.

        Returns the list of edges that terminate at the specified node,
        enabling merge node coordination and upstream task tracking.

        Args:
            node_id: The ID of the node to query.

        Returns:
            List of Edge objects terminating at the node. Returns empty list
            if the node has no inbound edges (e.g., START nodes).
        """
        return self.reverse_adjacency.get(node_id, [])

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
        return True

    def has_cycles(self) -> bool:
        """Detect cycles in the DAG."""
        visited = set()
        stack = set()

        def visit(node_id: str) -> bool:
            if node_id in stack:
                return True
            if node_id in visited:
                return False
            visited.add(node_id)
            stack.add(node_id)
            for edge in self.get_outbound_edges(node_id):
                if visit(edge.to_node_id):
                    return True
            stack.remove(node_id)
            return False

        for node_id in self.nodes.keys():
            if visit(node_id):
                return True
        return False

    def get_reachable_nodes(self, start_node_id: str) -> List[Node]:
        """Return list of nodes reachable from the given start node."""
        reachable_ids = set()
        stack = [start_node_id]
        while stack:
            current = stack.pop()
            if current in reachable_ids:
                continue
            reachable_ids.add(current)
            for edge in self.get_outbound_edges(current):
                stack.append(edge.to_node_id)
        return [self.nodes[node_id] for node_id in reachable_ids if node_id in self.nodes]
