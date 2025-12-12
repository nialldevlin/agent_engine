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
from agent_engine.schemas import Node, NodeRole, Task, TaskLifecycle, UniversalStatus, EngineError as EngineErrorRecord, EngineErrorCode, EngineErrorSource, Severity
from agent_engine.schemas.router import MergeInputItem
from agent_engine.dag import DAG


class Router:
    """Complete Router implementation for Agent Engine.

    Implements deterministic DAG traversal with worklist-based execution model.
    Handles all 7 canonical node roles: START, LINEAR, DECISION, BRANCH, SPLIT, MERGE, EXIT.
    """

    def __init__(self, dag: DAG = None, task_manager=None, node_executor=None, telemetry=None, metadata=None, workflow=None, stages=None):
        """Initialize router with DAG and runtime dependencies.

        Args:
            dag: The workflow DAG with nodes and edges
            task_manager: TaskManager instance for task lifecycle operations
            node_executor: NodeExecutor instance for single-node execution
            telemetry: Optional TelemetryBus instance for event emission
            metadata: Optional EngineMetadata instance for event metadata (Phase 11)
            workflow: Optional WorkflowGraph (tests) - converted to DAG
            stages: Optional mapping of stage_id -> Node (tests) used with workflow
        """
        if dag is None and workflow is not None and stages is not None:
            from agent_engine.dag import DAG
            # Build DAG from workflow graph and provided stage mapping
            node_map = {node_id: stages[node_id] for node_id in workflow.nodes}
            dag = DAG(nodes=node_map, edges=workflow.edges)
            self.stages = stages
        self.dag = dag
        # Provide default task manager/node executor for lightweight unit tests if not supplied
        from agent_engine.runtime.task_manager import TaskManager
        self.task_manager = task_manager or TaskManager()

        if node_executor is None:
            from agent_engine.schemas import StageExecutionRecord, UniversalStatus

            class _StubNodeExecutor:
                def execute_node(self, task, node):
                    record = StageExecutionRecord(
                        stage_id=getattr(node, "stage_id", None),
                        node_id=getattr(node, "stage_id", None),
                        node_role=node.role,
                        node_kind=node.kind,
                        node_status=UniversalStatus.SUCCESS,
                        input=task.current_output,
                        output=task.current_output,
                        started_at=datetime.utcnow().isoformat(),
                        completed_at=datetime.utcnow().isoformat(),
                    )
                    return record, task.current_output

            self.node_executor = _StubNodeExecutor()
        else:
            self.node_executor = node_executor
        self.telemetry = telemetry
        self.metadata = metadata

        # Execution state
        self.work_queue: List[tuple] = []  # List of (task_id, node_id) tuples
        self.task_queue = self.work_queue  # legacy alias for tests
        self.parent_children: Dict[str, Set[str]] = {}  # parent_task_id -> set of child_task_ids
        self.merge_waits: Dict[str, Dict] = {}  # (merge_node_id, parent_task_id) -> wait state

    # Compatibility API for DAGExecutor-based runtimes (legacy v0)
    def next_stage(self, current_stage_id: Optional[str], decision: Optional[dict] = None) -> Optional[str]:
        """Determine the next stage ID given current stage and optional decision output."""
        if current_stage_id is None:
            # Start of workflow
            start_node = self.dag.get_default_start_node()
            return start_node.stage_id

        edges = self.dag.get_outbound_edges(current_stage_id)
        if not edges:
            return None

        current_node = self.dag.nodes.get(current_stage_id)
        if current_node and current_node.role == NodeRole.DECISION:
            return self.resolve_edge(None, current_node, decision or {}, edges)

        # Non-decision: deterministic routing (first edge if multiple)
        return edges[0].to_node_id

    def resolve_edge(self, task, node, decision_output: Any, edges: List[Any]) -> str:
        """Resolve outbound edge for decision nodes based on decision output."""
        if not edges:
            raise ValueError("No outbound edges to resolve")
        if len(edges) == 1:
            return edges[0].to_node_id

        selected = None
        if isinstance(decision_output, dict):
            for key in ["condition", "route", "selected_edge", "selected_edge_label"]:
                if key in decision_output and decision_output[key] is not None:
                    selected = decision_output[key]
                    break
        else:
            selected = decision_output

        for edge in edges:
            if selected is None:
                continue
            if getattr(edge, "condition", None) == selected or getattr(edge, "label", None) == selected:
                return edge.to_node_id

        # Fallback: deterministic first edge
        return edges[0].to_node_id

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
        # Reset transient state for fresh execution
        self.work_queue.clear()
        self.parent_children.clear()

        task_spec = TaskSpec(
            task_spec_id=f"task_spec_{uuid.uuid4().hex[:8]}",
            request=str(input_payload),
            mode=TaskMode.IMPLEMENT
        )
        task = self.task_manager.create_task(spec=task_spec)
        task.current_output = input_payload
        # Mark task as in progress for execution lifecycle
        from agent_engine.schemas import UniversalStatus
        task.status = UniversalStatus.IN_PROGRESS

        if self.telemetry:
            self.telemetry.task_started(task_id=task.task_id, spec=task_spec, mode=task_spec.mode.value)

        # Step 11.3: Execute start node
        start_record, start_output = self.node_executor.execute_node(task, start_node)
        task.history.append(start_record)
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
                    f"Start node '{start_node_id}' not found in workflow DAG"
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

    def _process_worklist(self) -> Optional[tuple]:
        """Legacy helper used in tests: dequeue one item FIFO."""
        if not self.work_queue:
            return None
        return self.work_queue.pop(0)

    def _process_worklist_full(self) -> Optional[Task]:
        """Process worklist until completion or stall."""
        max_iterations = 10000  # Prevent infinite loops
        iterations = 0

        while self.work_queue and iterations < max_iterations:
            iterations += 1
            item = self.work_queue.pop(0)  # FIFO
            if isinstance(item, tuple):
                task_id, node_id = item
                task = self.task_manager.get_task(task_id)
            else:
                task = item
                task_id = task.task_id if task else None
                node_id = getattr(task, "current_stage_id", None)

            if not task or not node_id:
                continue  # Task or node missing, skip

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

            # Update task history
            task.history.append(record)

            # Check if node failed (Phase 7: continue_on_failure)
            node_failed = (record.node_status == UniversalStatus.FAILED)

            if node_failed:
                # Node failed - check continue_on_failure
                if node.continue_on_failure:
                    # Continue execution despite failure
                    # Task status may become PARTIAL if this was critical
                    # For now, continue to routing
                    pass
                else:
                    # Halt execution - fail the task
                    task.status = UniversalStatus.FAILED
                    task.lifecycle = TaskLifecycle.CONCLUDED
                    return task  # Stop execution

            # Update current output if execution succeeded
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
            if len(edges) == 0:
                raise EngineError(f"START node '{node.stage_id}' has no outbound edge")
            raise EngineError(
                f"START node '{node.stage_id}' must have exactly 1 outbound edges, has {len(edges)}"
            )
        target = edges[0].to_node_id
        if target not in self.dag.nodes:
            raise EngineError(f"invalid target node '{target}' not found in workflow")
        return target

    def _route_linear(self, task: Task, node: Node) -> str:
        """Route from LINEAR node (exactly 1 outbound edge)."""
        edges = self.dag.get_outbound_edges(node.stage_id)
        if len(edges) != 1:
            if len(edges) == 0:
                raise EngineError(f"LINEAR node '{node.stage_id}' has no outbound edge")
            raise EngineError(
                f"LINEAR node '{node.stage_id}' must have exactly 1 outbound edges, has {len(edges)}"
            )
        next_node_id = edges[0].to_node_id
        if next_node_id not in self.dag.nodes:
            raise EngineError(f"invalid target node '{next_node_id}' not found in workflow")

        # Emit routing decision event
        if self.telemetry:
            self.telemetry.routing_decision(
                task_id=task.task_id,
                node_id=node.stage_id,
                decision="linear",
                next_node_id=next_node_id
            )

        return next_node_id

    def _route_decision(self, task: Task, node: Node, output: Any) -> str:
        """Route from DECISION node (select one of multiple edges)."""
        edges = self.dag.get_outbound_edges(node.stage_id)
        if len(edges) < 2:
            if len(edges) == 0:
                raise EngineError(f"DECISION node '{node.stage_id}' has no outbound edges")
            raise EngineError(
                f"DECISION node '{node.stage_id}' must have at least 2 outbound edges, has {len(edges)}"
            )

        # Extract selected edge label from output
        selected_label = self._extract_selected_edge(output)

        # Match against edge labels
        for edge in edges:
            edge_label = getattr(edge, "label", None) or edge.condition
            if edge_label == selected_label:
                next_node_id = edge.to_node_id

                # Emit routing decision event
                if self.telemetry:
                    self.telemetry.routing_decision(
                        task_id=task.task_id,
                        node_id=node.stage_id,
                        decision=selected_label,
                        next_node_id=next_node_id
                    )

                return next_node_id

        # No match found
        valid_labels = [getattr(e, "label", None) or e.condition for e in edges]
        raise EngineError(
            f"Decision node '{node.stage_id}' selected edge '{selected_label}' does not match any outbound edge. "
            f"Valid labels: {valid_labels}"
        )

    def _extract_selected_edge(self, output: Any) -> str:
        """Extract selected_edge_label from decision output."""
        if output is None:
            raise EngineError("Decision output is None")

        # Handle dict output
        if isinstance(output, dict):
            if "selected_edge" in output and output["selected_edge"] is not None:
                return str(output["selected_edge"])
            if "selected_edge_label" in output:
                return str(output["selected_edge_label"])
            # Fallback to other common keys
            for key in ["condition", "route", "next"]:
                if key in output:
                    return str(output[key])
            raise EngineError(
                f"Cannot extract selected edge from output keys: {list(output.keys())}"
            )

        # Handle non-dict output (treat as label directly)
        return str(output)

    def _route_branch(self, task: Task, node: Node, task_manager=None) -> Optional[EngineErrorRecord]:
        """Route from BRANCH node (create clones for parallel execution).

        Returns EngineErrorRecord on validation failure, None on success.
        """
        tm = task_manager or self.task_manager

        def _err(error_id: str, message: str) -> EngineErrorRecord:
            return EngineErrorRecord(
                error_id=error_id,
                code=EngineErrorCode.ROUTING,
                message=message,
                source=EngineErrorSource.ROUTER,
                severity=Severity.ERROR,
                stage_id=node.stage_id,
                task_id=task.task_id,
            )

        if node.role != NodeRole.BRANCH:
            return _err("invalid_node_role", f"_route_branch called on non-BRANCH node '{node.stage_id}'")

        edges = self.dag.get_outbound_edges(node.stage_id)
        if len(edges) < 2:
            return _err("insufficient_edges", f"BRANCH node '{node.stage_id}' must have at least 2 outbound edges")

        # Validate target nodes exist
        for edge in edges:
            if edge.to_node_id not in self.dag.nodes:
                return _err("invalid_target_node", f"Target node '{edge.to_node_id}' not found in workflow")

        if task.task_id not in self.parent_children:
            self.parent_children[task.task_id] = set()

        clone_ids: List[str] = []
        for index, edge in enumerate(edges):
            branch_label = edge.condition or edge.to_node_id
            clone = tm.create_clone(parent=task, branch_label=branch_label, output=task.current_output)
            tm.set_current_stage(clone, edge.to_node_id)
            self.parent_children[task.task_id].add(clone.task_id)
            clone_ids.append(clone.task_id)
            # Enqueue clone task object (tests expect Task entries)
            self.task_queue.append(clone)

        if self.telemetry:
            self.telemetry.routing_branch(
                task_id=task.task_id,
                node_id=node.stage_id,
                clone_count=len(clone_ids),
                clone_ids=clone_ids,
            )

        return None

    def _route_split(self, task: Task, node: Node, output: Any, task_manager=None) -> Optional[EngineErrorRecord]:
        """Route from SPLIT node (create subtasks for hierarchical decomposition).

        Returns EngineErrorRecord on validation failure, None on success.
        """
        tm = task_manager or self.task_manager

        def _err(error_id: str, message: str) -> EngineErrorRecord:
            return EngineErrorRecord(
                error_id=error_id,
                code=EngineErrorCode.ROUTING,
                message=message,
                source=EngineErrorSource.ROUTER,
                severity=Severity.ERROR,
                stage_id=node.stage_id,
                task_id=task.task_id,
            )

        if node.role != NodeRole.SPLIT:
            return _err("invalid_node_role", f"_route_split called on non-SPLIT node '{node.stage_id}'")

        edges = self.dag.get_outbound_edges(node.stage_id)
        if len(edges) < 1:
            return _err("no_outbound_edges", f"SPLIT node '{node.stage_id}' must have at least 1 outbound edge")

        # Validate targets
        for edge in edges:
            if edge.to_node_id not in self.dag.nodes:
                return _err("invalid_target_node", f"Target node '{edge.to_node_id}' not found in workflow")

        # Extract subtask inputs
        subtask_inputs: Optional[List[Any]] = None
        if isinstance(output, dict):
            if "subtask_inputs" not in output:
                return _err("invalid_split_output", "SPLIT output missing 'subtask_inputs'")
            subtask_inputs = output.get("subtask_inputs")
        elif isinstance(output, list):
            subtask_inputs = output
        else:
            return _err("invalid_split_output", "SPLIT output must be dict with 'subtask_inputs' or a list")

        if not isinstance(subtask_inputs, list):
            return _err("invalid_output_type", "subtask_inputs must be a list")
        if len(subtask_inputs) == 0:
            return _err("empty_subtask_inputs", "subtask_inputs cannot be empty")

        if task.task_id not in self.parent_children:
            self.parent_children[task.task_id] = set()

        subtask_ids: List[str] = []
        for index, subtask_input in enumerate(subtask_inputs):
            edge = edges[index % len(edges)]
            split_edge_label = edge.condition or edge.to_node_id
            subtask = tm.create_subtask(parent=task, subtask_input=subtask_input, split_edge_label=split_edge_label)
            tm.set_current_stage(subtask, edge.to_node_id)
            self.parent_children[task.task_id].add(subtask.task_id)
            subtask_ids.append(subtask.task_id)
            # Enqueue subtask Task object
            self.task_queue.append(subtask)

        if self.telemetry:
            self.telemetry.routing_split(
                task_id=task.task_id,
                node_id=node.stage_id,
                subtask_count=len(subtask_ids),
                subtask_ids=subtask_ids,
            )

        return None

    def _route_merge(self, task: Task, node: Node) -> str:
        """Route from MERGE node (wait for all inbound, then recombine).

        Per Phase 7: Handle merge failure modes per node configuration.
        """
        parent_id = task.parent_task_id or task.task_id

        # Check if merge is ready (all required inputs arrived)
        if not self._check_merge_ready(node.stage_id, parent_id):
            # Not ready yet, will be re-queued by worklist processor
            return None

        # Assemble merge inputs from all completed children
        merge_inputs = self._assemble_merge_inputs(node.stage_id, parent_id)

        # Check for failures in upstream tasks (Phase 7)
        failed_inputs = [inp for inp in merge_inputs if inp.status == UniversalStatus.FAILED]
        successful_inputs = [inp for inp in merge_inputs if inp.status == UniversalStatus.COMPLETED]

        # Emit merge event
        input_statuses = [inp.status for inp in merge_inputs]
        if self.telemetry:
            self.telemetry.routing_merge(
                task_id=task.task_id,
                node_id=node.stage_id,
                input_count=len(merge_inputs),
                input_statuses=input_statuses
            )

        # Apply merge failure mode (Phase 7)
        failure_mode = node.merge_failure_mode or "fail_on_any"

        # Get parent task
        parent_task = self.task_manager.get_task(parent_id)

        if failure_mode == "fail_on_any":
            if failed_inputs:
                # Fail the merge task
                parent_task.status = UniversalStatus.FAILED
                # Continue to routing, but task is marked as failed

        elif failure_mode == "ignore_failures":
            # Only pass successful inputs to merge node
            merge_inputs = successful_inputs
            # Task status remains based on merge output

        elif failure_mode == "partial":
            if failed_inputs and successful_inputs:
                # Mixed success/failure → PARTIAL
                parent_task.status = UniversalStatus.PARTIAL
            elif failed_inputs:
                # All failed → FAILED
                parent_task.status = UniversalStatus.FAILED
            # else: all successful → keep status as is

        # Create merge payload
        merge_payload = {"merge_inputs": [item.dict() for item in merge_inputs]}

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
            # No spawned children: treat merge as immediately ready
            return True

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
        task.lifecycle = TaskLifecycle.CONCLUDED

        # Set final status if not already set
        if task.status in (UniversalStatus.PENDING, UniversalStatus.IN_PROGRESS):
            task.status = UniversalStatus.COMPLETED

        # Apply always_fail override if specified (Phase 7)
        if node.always_fail:
            task.status = UniversalStatus.FAILED

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
