"""Router - Canonical DAG routing for Agent Engine.

Implements deterministic DAG traversal with worklist-based execution model.
Handles all 7 canonical node roles per AGENT_ENGINE_SPEC §3.1 and Phase 5:
START, LINEAR, DECISION, BRANCH, SPLIT, MERGE, EXIT.

Complete Phase 5 implementation with all routing semantics.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set
from datetime import datetime

from agent_engine.exceptions import EngineError
from agent_engine.schemas import Node, NodeRole, Task, TaskLifecycle, UniversalStatus
from agent_engine.schemas.router import MergeInputItem
from agent_engine.dag import DAG


class Router:
    """Complete Router implementation for Agent Engine.

    Implements deterministic DAG traversal with worklist-based execution model.
    Handles all 7 canonical node roles: START, LINEAR, DECISION, BRANCH, SPLIT, MERGE, EXIT.
    """

    def __init__(self, dag: DAG, task_manager, node_executor):
        """Initialize router with DAG and runtime dependencies.

        Args:
            dag: The workflow DAG with nodes and edges
            task_manager: TaskManager instance for task lifecycle operations
            node_executor: NodeExecutor instance for single-node execution
        """
        self.dag = dag
        self.task_manager = task_manager
        self.node_executor = node_executor

        # Execution state
        self.work_queue: List[tuple] = []  # List of (task_id, node_id) tuples
        self.parent_children: Dict[str, Set[str]] = {}  # parent_task_id -> set of child_task_ids
        self.merge_waits: Dict[str, Dict] = {}  # (merge_node_id, parent_task_id) -> wait state

    def execute_task(self, input_payload: Any, start_node_id: Optional[str] = None) -> Task:
        """Main entry point for task execution.

        Executes a complete workflow from start to exit following DAG routing semantics.

        Args:
            input_payload: Input data for the workflow
            start_node_id: Optional explicit start node ID (uses default if None)

        Returns:
            Completed Task with full execution history

        Raises:
            EngineError: If routing fails or execution stalls
        """
        # Step 11.1: Select start node
        start_node = self._select_start_node(start_node_id)

        # Step 11.2: Create initial task
        from agent_engine.schemas.task import TaskSpec, TaskMode
        import uuid
        task_spec = TaskSpec(
            task_spec_id=f"task_spec_{uuid.uuid4().hex[:8]}",
            request=str(input_payload),
            mode=TaskMode.IMPLEMENT
        )
        task = self.task_manager.create_task(spec=task_spec)

        # Step 11.3: Execute start node
        start_record, start_output = self.node_executor.execute_node(task, start_node)
        if start_output is not None:
            task.current_output = start_output

        # Step 11.4: Route from start node
        next_node_id = self._route_by_role(task, start_node, task.current_output)
        if next_node_id:
            self._enqueue_work(task.task_id, next_node_id)

        # Step 11.5: Process worklist
        final_task = self._process_worklist_full()

        # Step 11.6: Return completed task
        return final_task if final_task else task

    def _select_start_node(self, start_node_id: Optional[str] = None) -> Node:
        """Select the start node (default or explicit)."""
        if start_node_id is not None:
            if start_node_id not in self.dag.nodes:
                raise EngineError(
                    f"Start node '{start_node_id}' not found in DAG"
                )
            node = self.dag.nodes[start_node_id]
            if node.role != NodeRole.START:
                raise EngineError(
                    f"Node '{start_node_id}' has role '{node.role}', expected 'start'"
                )
            return node
        else:
            # Find default start node
            for node_id, node in self.dag.nodes.items():
                if node.role == NodeRole.START and getattr(node, 'default_start', False):
                    return node
            raise EngineError("No default start node found in DAG")

    def _enqueue_work(self, task_id: str, node_id: str) -> None:
        """Enqueue work item for processing."""
        self.work_queue.append((task_id, node_id))

    def _process_worklist_full(self) -> Optional[Task]:
        """Process worklist until completion or stall."""
        max_iterations = 10000  # Prevent infinite loops
        iterations = 0

        while self.work_queue and iterations < max_iterations:
            iterations += 1
            task_id, node_id = self.work_queue.pop(0)  # FIFO

            # Retrieve task and node
            task = self.task_manager.get_task(task_id)
            if not task:
                continue  # Task no longer exists

            node = self.dag.nodes.get(node_id)
            if not node:
                raise EngineError(f"Node '{node_id}' not found in DAG")

            # Skip merge nodes that aren't ready yet
            if node.role == NodeRole.MERGE:
                parent_id = task.parent_task_id or task.task_id
                if not self._check_merge_ready(node.stage_id, parent_id):
                    self.work_queue.append((task_id, node_id))  # Re-queue for later
                    continue

            # Execute node
            record, output = self.node_executor.execute_node(task, node)
            if output is not None:
                task.current_output = output

            # Route based on node role
            next_node_id = self._route_by_role(task, node, output)

            # Handle EXIT nodes
            if node.role == NodeRole.EXIT:
                return task  # Execution complete

            # Enqueue next work if routing produced a node ID
            if next_node_id:
                self._enqueue_work(task.task_id, next_node_id)

        if iterations >= max_iterations:
            raise EngineError("Execution stalled: maximum iterations exceeded")

        return None

    def _route_by_role(self, task: Task, node: Node, output: Any) -> Optional[str]:
        """Dispatch routing based on node role."""
        if node.role == NodeRole.START:
            return self._route_start(task, node)
        elif node.role == NodeRole.LINEAR:
            return self._route_linear(task, node)
        elif node.role == NodeRole.DECISION:
            return self._route_decision(task, node, output)
        elif node.role == NodeRole.BRANCH:
            return self._route_branch(task, node)
        elif node.role == NodeRole.SPLIT:
            return self._route_split(task, node, output)
        elif node.role == NodeRole.MERGE:
            return self._route_merge(task, node)
        elif node.role == NodeRole.EXIT:
            return self._route_exit(task, node)
        else:
            raise EngineError(f"Unknown node role: {node.role}")

    def _route_start(self, task: Task, node: Node) -> str:
        """Route from START node (exactly 1 outbound edge)."""
        edges = self.dag.get_outbound_edges(node.stage_id)
        if len(edges) != 1:
            raise EngineError(
                f"START node '{node.stage_id}' must have exactly 1 outbound edge, has {len(edges)}"
            )
        return edges[0].to_node_id

    def _route_linear(self, task: Task, node: Node) -> str:
        """Route from LINEAR node (exactly 1 outbound edge)."""
        edges = self.dag.get_outbound_edges(node.stage_id)
        if len(edges) != 1:
            raise EngineError(
                f"LINEAR node '{node.stage_id}' must have exactly 1 outbound edge, has {len(edges)}"
            )
        return edges[0].to_node_id

    def _route_decision(self, task: Task, node: Node, output: Any) -> str:
        """Route from DECISION node (select one of multiple edges)."""
        edges = self.dag.get_outbound_edges(node.stage_id)
        if len(edges) < 2:
            raise EngineError(
                f"DECISION node '{node.stage_id}' must have at least 2 outbound edges, has {len(edges)}"
            )

        # Extract selected edge label from output
        selected_label = self._extract_selected_edge(output)

        # Match against edge labels
        for edge in edges:
            if edge.label == selected_label:
                return edge.to_node_id

        # No match found
        valid_labels = [e.label for e in edges if e.label]
        raise EngineError(
            f"Decision node '{node.stage_id}' selected invalid edge label '{selected_label}'. "
            f"Valid labels: {valid_labels}"
        )

    def _extract_selected_edge(self, output: Any) -> str:
        """Extract selected_edge_label from decision output."""
        if output is None:
            raise EngineError("Decision output is None")

        # Handle dict output
        if isinstance(output, dict):
            if "selected_edge_label" in output:
                return str(output["selected_edge_label"])
            # Fallback to other common keys
            for key in ["condition", "route", "next"]:
                if key in output:
                    return str(output[key])
            raise EngineError(
                f"Decision output must contain 'selected_edge_label' field. Got: {list(output.keys())}"
            )

        # Handle non-dict output (treat as label directly)
        return str(output)

    def _route_branch(self, task: Task, node: Node) -> None:
        """Route from BRANCH node (create clones for parallel execution)."""
        edges = self.dag.get_outbound_edges(node.stage_id)
        if len(edges) < 2:
            raise EngineError(
                f"BRANCH node '{node.stage_id}' must have at least 2 outbound edges, has {len(edges)}"
            )

        # Initialize parent-children tracking
        if task.task_id not in self.parent_children:
            self.parent_children[task.task_id] = set()

        # Create clone for each outbound edge
        for i, edge in enumerate(edges):
            clone = self.task_manager.create_clone(
                parent_task_id=task.task_id,
                branch_node_id=node.stage_id,
                branch_label=edge.label or f"branch_{i}"
            )
            self.parent_children[task.task_id].add(clone.task_id)
            self._enqueue_work(clone.task_id, edge.to_node_id)

        # No next node for parent (clones continue execution)
        return None

    def _route_split(self, task: Task, node: Node, output: Any) -> None:
        """Route from SPLIT node (create subtasks for hierarchical decomposition)."""
        edges = self.dag.get_outbound_edges(node.stage_id)
        if len(edges) < 1:
            raise EngineError(
                f"SPLIT node '{node.stage_id}' must have at least 1 outbound edge"
            )

        # Extract subtask inputs from output
        if isinstance(output, dict) and "subtask_inputs" in output:
            subtask_inputs = output["subtask_inputs"]
        elif isinstance(output, list):
            subtask_inputs = output
        else:
            raise EngineError(
                f"SPLIT node output must contain 'subtask_inputs' list or be a list. Got: {type(output)}"
            )

        if not isinstance(subtask_inputs, list):
            raise EngineError(
                f"Subtask inputs must be a list, got: {type(subtask_inputs)}"
            )

        # Initialize parent-children tracking
        if task.task_id not in self.parent_children:
            self.parent_children[task.task_id] = set()

        # Create subtask for each input
        for i, subtask_input in enumerate(subtask_inputs):
            # Determine which edge to use (round-robin if multiple edges)
            edge = edges[i % len(edges)]

            subtask = self.task_manager.create_subtask(
                parent_task_id=task.task_id,
                split_node_id=node.stage_id,
                split_label=edge.label or f"subtask_{i}",
                subtask_input=subtask_input
            )
            self.parent_children[task.task_id].add(subtask.task_id)
            self._enqueue_work(subtask.task_id, edge.to_node_id)

        # No next node for parent (subtasks continue execution)
        return None

    def _route_merge(self, task: Task, node: Node) -> str:
        """Route from MERGE node (wait for all inbound, then recombine)."""
        parent_id = task.parent_task_id or task.task_id

        # Check if merge is ready (all required inputs arrived)
        if not self._check_merge_ready(node.stage_id, parent_id):
            # Not ready yet, will be re-queued by worklist processor
            return None

        # Assemble merge inputs from all completed children
        merge_inputs = self._assemble_merge_inputs(node.stage_id, parent_id)

        # Create merge payload
        merge_payload = {"merge_inputs": [item.dict() for item in merge_inputs]}

        # Get parent task
        parent_task = self.task_manager.get_task(parent_id)

        # Execute merge node with assembled input
        merge_record, merge_output = self.node_executor.execute_node(parent_task, node)
        # TODO: Pass merge_payload to node executor properly

        # Recombine into parent task (v1 always recombines)
        parent_task.current_output = merge_output

        # Continue with parent task on single outbound edge
        edges = self.dag.get_outbound_edges(node.stage_id)
        if len(edges) != 1:
            raise EngineError(
                f"MERGE node '{node.stage_id}' must have exactly 1 outbound edge, has {len(edges)}"
            )

        return edges[0].to_node_id

    def _check_merge_ready(self, merge_node_id: str, parent_task_id: str) -> bool:
        """Check if merge node has all required inputs."""
        parent_task = self.task_manager.get_task(parent_task_id)
        if not parent_task:
            return False

        children = self.parent_children.get(parent_task_id, set())
        if not children:
            return False

        # Determine completion criteria based on lineage type
        # Inspect first child to determine type
        first_child_id = next(iter(children))
        first_child = self.task_manager.get_task(first_child_id)

        if first_child and first_child.lineage_type == "clone":
            # For clones: merge ready when ANY clone completes
            return self.task_manager.check_clone_completion(parent_task_id)
        elif first_child and first_child.lineage_type == "subtask":
            # For subtasks: merge ready when ALL subtasks complete
            return self.task_manager.check_subtask_completion(parent_task_id)

        return False

    def _assemble_merge_inputs(self, merge_node_id: str, parent_task_id: str) -> List[MergeInputItem]:
        """Assemble merge inputs from completed children."""
        merge_inputs = []

        children = self.parent_children.get(parent_task_id, set())
        for child_id in children:
            child_task = self.task_manager.get_task(child_id)
            if not child_task:
                continue

            # Only include successfully completed tasks
            if child_task.status == UniversalStatus.COMPLETED:
                # Get most recent stage execution record
                if child_task.history:
                    last_record = child_task.history[-1]
                    merge_input = MergeInputItem(
                        task_id=child_task.task_id,
                        node_id=last_record.node_id or "unknown",
                        status=child_task.status.value,
                        output=child_task.current_output,
                        stage_result_index=len(child_task.history) - 1,
                        timestamp=last_record.completed_at or datetime.utcnow().isoformat(),
                        lineage_metadata={
                            "type": child_task.lineage_type,
                            "parent_task_id": parent_task_id
                        }
                    )
                    merge_inputs.append(merge_input)

        return merge_inputs

    def _route_exit(self, task: Task, node: Node) -> None:
        """Route from EXIT node (finalize and halt)."""
        # Mark task as completed
        task.lifecycle = TaskLifecycle.COMPLETED

        # Set final status if not already set
        if task.status == UniversalStatus.PENDING:
            task.status = UniversalStatus.COMPLETED

        # Check parent completion if this is a clone/subtask
        if task.parent_task_id:
            parent_task = self.task_manager.get_task(task.parent_task_id)
            if parent_task:
                if task.lineage_type == "clone":
                    if self.task_manager.check_clone_completion(task.parent_task_id):
                        parent_task.status = UniversalStatus.COMPLETED
                        parent_task.lifecycle = TaskLifecycle.COMPLETED
                elif task.lineage_type == "subtask":
                    if self.task_manager.check_subtask_completion(task.parent_task_id):
                        parent_task.status = UniversalStatus.COMPLETED
                        parent_task.lifecycle = TaskLifecycle.COMPLETED

        # No next node (execution halts)
        return None
