"""Router handles DAG routing and stage transitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from agent_engine.schemas import Node, WorkflowGraph


@dataclass
class Router:
    workflow: WorkflowGraph
    stages: Dict[str, Node]

    def next_stage(self, current_stage_id: Optional[str], decision: Optional[dict] = None) -> Optional[str]:
        if current_stage_id is None:
            # Find the default start node (role == START and default_start == True)
            for node_id, node in self.stages.items():
                if hasattr(node, 'default_start') and node.default_start:
                    return node_id
            return None
        outgoing = [e for e in self.workflow.edges if e.from_node_id == current_stage_id]
        if not outgoing:
            return None

        # decision-based routing
        if decision:
            condition = decision.get("condition") or decision.get("route") or decision.get("next")
            if condition:
                for edge in outgoing:
                    if edge.condition == condition or edge.to_node_id == condition:
                        return edge.to_node_id
        # default: single edge or first
        return outgoing[0].to_node_id

    def workflow_stage_lookup(self, stage_id: str) -> Node:
        return self.stages[stage_id]

    def resolve_edge(self, task, node, decision_output: dict, edges: list) -> str:
        """Deterministically resolve which edge to follow based on decision output.

        Args:
            task: Current Task object.
            node: Current Node object.
            decision_output: Output from a decision node (typically a dict).
            edges: List of Edge objects from the current node.

        Returns:
            to_node_id (str): The next node ID to transition to.

        Raises:
            ValueError: If edges is empty.

        Deterministic routing policy:
        1. If decision_output contains "condition", "route", or "next" (in that order),
           extract the condition value and find the first edge where
           edge.condition == condition or edge.to_node_id == condition.
        2. If no condition matches and len(edges) == 1, return edges[0].to_node_id.
        3. If multiple edges exist and none match, return edges[0].to_node_id (default).
        """
        if not edges:
            raise ValueError("Cannot resolve edge: edges list is empty")

        if not isinstance(decision_output, dict):
            decision_output = {}

        # Try to extract condition in order: condition, route, next
        condition = decision_output.get("condition") or decision_output.get("route") or decision_output.get("next")

        # If a condition was found, search for a matching edge
        if condition:
            for edge in edges:
                if edge.condition == condition or edge.to_node_id == condition:
                    return edge.to_node_id

        # Default: single edge or first edge
        return edges[0].to_node_id
