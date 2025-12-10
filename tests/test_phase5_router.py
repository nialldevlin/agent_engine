"""Phase 5 Tests: Router v1.0 (Deterministic DAG Routing).

Tests for Steps 7 and 8 implementation:
- Step 7: _route_branch - Clone creation from BRANCH nodes
- Step 8: _route_split - Subtask creation from SPLIT nodes

Per AGENT_ENGINE_SPEC §3.1 and OVERVIEW §1.3-1.5.
"""

import pytest
from agent_engine.runtime.router import Router
from agent_engine.runtime.task_manager import TaskManager
from agent_engine.schemas import (
    Edge,
    EngineErrorCode,
    EngineErrorSource,
    Node,
    NodeKind,
    NodeRole,
    TaskMode,
    TaskSpec,
    UniversalStatus,
    WorkflowGraph,
)


class TestRouteBranch:
    """Tests for Router._route_branch method (Step 7)."""

    def test_branch_creates_clones_for_each_edge(self) -> None:
        """Test that _route_branch creates one clone per outbound edge."""
        # Setup
        stages = {
            "start": Node(
                stage_id="start",
                name="Start",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.START,
                default_start=True,
                context="global",
            ),
            "branch": Node(
                stage_id="branch",
                name="Branch Node",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.BRANCH,
                context="global",
            ),
            "path1": Node(
                stage_id="path1",
                name="Path 1",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.LINEAR,
                context="global",
            ),
            "path2": Node(
                stage_id="path2",
                name="Path 2",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.LINEAR,
                context="global",
            ),
            "exit": Node(
                stage_id="exit",
                name="Exit",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.EXIT,
                context="global",
            ),
        }
        workflow = WorkflowGraph(
            workflow_id="wf",
            nodes=list(stages.keys()),
            edges=[
                Edge(from_node_id="start", to_node_id="branch"),
                Edge(from_node_id="branch", to_node_id="path1", condition="path_a"),
                Edge(from_node_id="branch", to_node_id="path2", condition="path_b"),
                Edge(from_node_id="path1", to_node_id="exit"),
                Edge(from_node_id="path2", to_node_id="exit"),
            ],
        )
        router = Router(workflow=workflow, stages=stages)
        task_manager = TaskManager()

        spec = TaskSpec(task_spec_id="test", request="do", mode=TaskMode.ANALYSIS_ONLY)
        task = task_manager.create_task(spec)
        task.current_output = {"data": "test"}

        # Execute
        error = router._route_branch(task, stages["branch"], task_manager)

        # Verify no error
        assert error is None

        # Verify clones were created
        assert len(task.child_task_ids) == 2
        clones = task_manager.get_children(task.task_id)
        assert len(clones) == 2

        # Verify clone properties
        clone1, clone2 = clones
        assert clone1.lineage_type == "clone"
        assert clone2.lineage_type == "clone"
        assert clone1.parent_task_id == task.task_id
        assert clone2.parent_task_id == task.task_id

        # Verify clones have correct target nodes
        clone_targets = {clone1.current_stage_id, clone2.current_stage_id}
        assert clone_targets == {"path1", "path2"}

    def test_branch_tracks_parent_children_relationship(self) -> None:
        """Test that _route_branch tracks parent→child relationships."""
        stages = {
            "start": Node(
                stage_id="start",
                name="Start",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.START,
                default_start=True,
                context="global",
            ),
            "branch": Node(
                stage_id="branch",
                name="Branch",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.BRANCH,
                context="global",
            ),
            "path1": Node(
                stage_id="path1",
                name="Path 1",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.LINEAR,
                context="global",
            ),
            "path2": Node(
                stage_id="path2",
                name="Path 2",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.LINEAR,
                context="global",
            ),
        }
        workflow = WorkflowGraph(
            workflow_id="wf",
            nodes=list(stages.keys()),
            edges=[
                Edge(from_node_id="start", to_node_id="branch"),
                Edge(from_node_id="branch", to_node_id="path1"),
                Edge(from_node_id="branch", to_node_id="path2"),
            ],
        )
        router = Router(workflow=workflow, stages=stages)
        task_manager = TaskManager()

        spec = TaskSpec(task_spec_id="test", request="do", mode=TaskMode.ANALYSIS_ONLY)
        task = task_manager.create_task(spec)

        # Execute
        router._route_branch(task, stages["branch"], task_manager)

        # Verify parent_children tracking
        assert task.task_id in router.parent_children
        assert len(router.parent_children[task.task_id]) == 2
        assert router.parent_children[task.task_id] == set(task.child_task_ids)

    def test_branch_enqueues_clones_in_task_queue(self) -> None:
        """Test that _route_branch enqueues clones in task_queue."""
        stages = {
            "branch": Node(
                stage_id="branch",
                name="Branch",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.BRANCH,
                context="global",
            ),
            "path1": Node(
                stage_id="path1",
                name="Path 1",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.LINEAR,
                context="global",
            ),
            "path2": Node(
                stage_id="path2",
                name="Path 2",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.LINEAR,
                context="global",
            ),
        }
        workflow = WorkflowGraph(
            workflow_id="wf",
            nodes=list(stages.keys()),
            edges=[
                Edge(from_node_id="branch", to_node_id="path1"),
                Edge(from_node_id="branch", to_node_id="path2"),
            ],
        )
        router = Router(workflow=workflow, stages=stages)
        task_manager = TaskManager()

        spec = TaskSpec(task_spec_id="test", request="do")
        task = task_manager.create_task(spec)

        # Execute
        router._route_branch(task, stages["branch"], task_manager)

        # Verify task_queue contains clones
        assert len(router.task_queue) == 2
        queued_ids = {t.task_id for t in router.task_queue}
        assert queued_ids == set(task.child_task_ids)

    def test_branch_rejects_non_branch_node(self) -> None:
        """Test that _route_branch rejects non-BRANCH nodes."""
        stages = {
            "linear": Node(
                stage_id="linear",
                name="Linear",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.LINEAR,
                context="global",
            ),
        }
        workflow = WorkflowGraph(
            workflow_id="wf", nodes=list(stages.keys()), edges=[]
        )
        router = Router(workflow=workflow, stages=stages)
        task_manager = TaskManager()

        spec = TaskSpec(task_spec_id="test", request="do")
        task = task_manager.create_task(spec)

        # Execute
        error = router._route_branch(task, stages["linear"], task_manager)

        # Verify error
        assert error is not None
        assert error.code == EngineErrorCode.ROUTING
        assert error.error_id == "invalid_node_role"
        assert "non-BRANCH" in error.message

    def test_branch_rejects_insufficient_edges(self) -> None:
        """Test that _route_branch rejects BRANCH nodes with <2 edges."""
        stages = {
            "branch": Node(
                stage_id="branch",
                name="Branch",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.BRANCH,
                context="global",
            ),
            "path1": Node(
                stage_id="path1",
                name="Path 1",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.LINEAR,
                context="global",
            ),
        }
        workflow = WorkflowGraph(
            workflow_id="wf",
            nodes=list(stages.keys()),
            edges=[Edge(from_node_id="branch", to_node_id="path1")],
        )
        router = Router(workflow=workflow, stages=stages)
        task_manager = TaskManager()

        spec = TaskSpec(task_spec_id="test", request="do")
        task = task_manager.create_task(spec)

        # Execute
        error = router._route_branch(task, stages["branch"], task_manager)

        # Verify error
        assert error is not None
        assert error.code == EngineErrorCode.ROUTING
        assert error.error_id == "insufficient_edges"

    def test_branch_inherits_parent_output(self) -> None:
        """Test that clones inherit parent's current_output."""
        stages = {
            "branch": Node(
                stage_id="branch",
                name="Branch",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.BRANCH,
                context="global",
            ),
            "path1": Node(
                stage_id="path1",
                name="Path 1",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.LINEAR,
                context="global",
            ),
            "path2": Node(
                stage_id="path2",
                name="Path 2",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.LINEAR,
                context="global",
            ),
        }
        workflow = WorkflowGraph(
            workflow_id="wf",
            nodes=list(stages.keys()),
            edges=[
                Edge(from_node_id="branch", to_node_id="path1"),
                Edge(from_node_id="branch", to_node_id="path2"),
            ],
        )
        router = Router(workflow=workflow, stages=stages)
        task_manager = TaskManager()

        spec = TaskSpec(task_spec_id="test", request="do")
        task = task_manager.create_task(spec)
        parent_output = {"key": "value", "count": 42}
        task.current_output = parent_output

        # Execute
        router._route_branch(task, stages["branch"], task_manager)

        # Verify clones inherit output
        clones = task_manager.get_children(task.task_id)
        for clone in clones:
            assert clone.current_output == parent_output

    def test_branch_uses_edge_condition_as_label(self) -> None:
        """Test that branch label comes from edge.condition when available."""
        stages = {
            "branch": Node(
                stage_id="branch",
                name="Branch",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.BRANCH,
                context="global",
            ),
            "path1": Node(
                stage_id="path1",
                name="Path 1",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.LINEAR,
                context="global",
            ),
            "path2": Node(
                stage_id="path2",
                name="Path 2",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.LINEAR,
                context="global",
            ),
        }
        workflow = WorkflowGraph(
            workflow_id="wf",
            nodes=list(stages.keys()),
            edges=[
                Edge(from_node_id="branch", to_node_id="path1", condition="option_a"),
                Edge(from_node_id="branch", to_node_id="path2", condition="option_b"),
            ],
        )
        router = Router(workflow=workflow, stages=stages)
        task_manager = TaskManager()

        spec = TaskSpec(task_spec_id="test", request="do")
        task = task_manager.create_task(spec)

        # Execute
        router._route_branch(task, stages["branch"], task_manager)

        # Verify branch labels
        clones = task_manager.get_children(task.task_id)
        branch_labels = {
            clone.lineage_metadata.get("branch_label") for clone in clones
        }
        assert branch_labels == {"option_a", "option_b"}


class TestRouteSplit:
    """Tests for Router._route_split method (Step 8)."""

    def test_split_creates_subtasks_from_dict_key(self) -> None:
        """Test that _route_split creates subtasks from output["subtask_inputs"]."""
        stages = {
            "split": Node(
                stage_id="split",
                name="Split",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.SPLIT,
                context="global",
            ),
            "work": Node(
                stage_id="work",
                name="Work",
                kind=NodeKind.AGENT,
                agent_id="agent1",
                role=NodeRole.LINEAR,
                context="global",
            ),
        }
        workflow = WorkflowGraph(
            workflow_id="wf",
            nodes=list(stages.keys()),
            edges=[Edge(from_node_id="split", to_node_id="work")],
        )
        router = Router(workflow=workflow, stages=stages)
        task_manager = TaskManager()

        spec = TaskSpec(task_spec_id="test", request="do")
        task = task_manager.create_task(spec)

        output = {
            "subtask_inputs": [
                {"task": 1},
                {"task": 2},
                {"task": 3},
            ]
        }

        # Execute
        error = router._route_split(task, stages["split"], output, task_manager)

        # Verify no error
        assert error is None

        # Verify subtasks created
        assert len(task.child_task_ids) == 3
        subtasks = task_manager.get_children(task.task_id)
        assert len(subtasks) == 3

        # Verify all are subtasks
        for subtask in subtasks:
            assert subtask.lineage_type == "subtask"
            assert subtask.parent_task_id == task.task_id

    def test_split_creates_subtasks_from_list_output(self) -> None:
        """Test that _route_split accepts direct list output."""
        stages = {
            "split": Node(
                stage_id="split",
                name="Split",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.SPLIT,
                context="global",
            ),
            "work": Node(
                stage_id="work",
                name="Work",
                kind=NodeKind.AGENT,
                agent_id="agent1",
                role=NodeRole.LINEAR,
                context="global",
            ),
        }
        workflow = WorkflowGraph(
            workflow_id="wf",
            nodes=list(stages.keys()),
            edges=[Edge(from_node_id="split", to_node_id="work")],
        )
        router = Router(workflow=workflow, stages=stages)
        task_manager = TaskManager()

        spec = TaskSpec(task_spec_id="test", request="do")
        task = task_manager.create_task(spec)

        # Direct list output
        output = [
            {"item": "a"},
            {"item": "b"},
        ]

        # Execute
        error = router._route_split(task, stages["split"], output, task_manager)

        # Verify no error
        assert error is None

        # Verify subtasks created
        assert len(task.child_task_ids) == 2
        subtasks = task_manager.get_children(task.task_id)
        assert len(subtasks) == 2

    def test_split_tracks_parent_children_relationship(self) -> None:
        """Test that _route_split tracks parent→child relationships."""
        stages = {
            "split": Node(
                stage_id="split",
                name="Split",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.SPLIT,
                context="global",
            ),
            "work": Node(
                stage_id="work",
                name="Work",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.LINEAR,
                context="global",
            ),
        }
        workflow = WorkflowGraph(
            workflow_id="wf",
            nodes=list(stages.keys()),
            edges=[Edge(from_node_id="split", to_node_id="work")],
        )
        router = Router(workflow=workflow, stages=stages)
        task_manager = TaskManager()

        spec = TaskSpec(task_spec_id="test", request="do")
        task = task_manager.create_task(spec)

        output = {"subtask_inputs": [{"id": 1}, {"id": 2}]}

        # Execute
        router._route_split(task, stages["split"], output, task_manager)

        # Verify parent_children tracking
        assert task.task_id in router.parent_children
        assert len(router.parent_children[task.task_id]) == 2
        assert router.parent_children[task.task_id] == set(task.child_task_ids)

    def test_split_enqueues_subtasks(self) -> None:
        """Test that _route_split enqueues subtasks in task_queue."""
        stages = {
            "split": Node(
                stage_id="split",
                name="Split",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.SPLIT,
                context="global",
            ),
            "work": Node(
                stage_id="work",
                name="Work",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.LINEAR,
                context="global",
            ),
        }
        workflow = WorkflowGraph(
            workflow_id="wf",
            nodes=list(stages.keys()),
            edges=[Edge(from_node_id="split", to_node_id="work")],
        )
        router = Router(workflow=workflow, stages=stages)
        task_manager = TaskManager()

        spec = TaskSpec(task_spec_id="test", request="do")
        task = task_manager.create_task(spec)

        output = {"subtask_inputs": [{"task": 1}, {"task": 2}]}

        # Execute
        router._route_split(task, stages["split"], output, task_manager)

        # Verify task_queue
        assert len(router.task_queue) == 2
        queued_ids = {t.task_id for t in router.task_queue}
        assert queued_ids == set(task.child_task_ids)

    def test_split_rejects_non_split_node(self) -> None:
        """Test that _route_split rejects non-SPLIT nodes."""
        stages = {
            "linear": Node(
                stage_id="linear",
                name="Linear",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.LINEAR,
                context="global",
            ),
        }
        workflow = WorkflowGraph(
            workflow_id="wf", nodes=list(stages.keys()), edges=[]
        )
        router = Router(workflow=workflow, stages=stages)
        task_manager = TaskManager()

        spec = TaskSpec(task_spec_id="test", request="do")
        task = task_manager.create_task(spec)

        output = {"subtask_inputs": [{"id": 1}]}

        # Execute
        error = router._route_split(task, stages["linear"], output, task_manager)

        # Verify error
        assert error is not None
        assert error.code == EngineErrorCode.ROUTING
        assert error.error_id == "invalid_node_role"

    def test_split_rejects_no_outbound_edges(self) -> None:
        """Test that _route_split rejects SPLIT nodes with 0 edges."""
        stages = {
            "split": Node(
                stage_id="split",
                name="Split",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.SPLIT,
                context="global",
            ),
        }
        workflow = WorkflowGraph(
            workflow_id="wf", nodes=list(stages.keys()), edges=[]
        )
        router = Router(workflow=workflow, stages=stages)
        task_manager = TaskManager()

        spec = TaskSpec(task_spec_id="test", request="do")
        task = task_manager.create_task(spec)

        output = {"subtask_inputs": [{"id": 1}]}

        # Execute
        error = router._route_split(task, stages["split"], output, task_manager)

        # Verify error
        assert error is not None
        assert error.code == EngineErrorCode.ROUTING
        assert error.error_id == "no_outbound_edges"

    def test_split_rejects_invalid_output_dict(self) -> None:
        """Test that _route_split rejects dicts without subtask_inputs key."""
        stages = {
            "split": Node(
                stage_id="split",
                name="Split",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.SPLIT,
                context="global",
            ),
            "work": Node(
                stage_id="work",
                name="Work",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.LINEAR,
                context="global",
            ),
        }
        workflow = WorkflowGraph(
            workflow_id="wf",
            nodes=list(stages.keys()),
            edges=[Edge(from_node_id="split", to_node_id="work")],
        )
        router = Router(workflow=workflow, stages=stages)
        task_manager = TaskManager()

        spec = TaskSpec(task_spec_id="test", request="do")
        task = task_manager.create_task(spec)

        # Dict without subtask_inputs key
        output = {"result": [1, 2, 3]}

        # Execute
        error = router._route_split(task, stages["split"], output, task_manager)

        # Verify error
        assert error is not None
        assert error.code == EngineErrorCode.ROUTING
        assert error.error_id == "invalid_split_output"

    def test_split_rejects_invalid_output_type(self) -> None:
        """Test that _route_split rejects non-dict/non-list outputs."""
        stages = {
            "split": Node(
                stage_id="split",
                name="Split",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.SPLIT,
                context="global",
            ),
            "work": Node(
                stage_id="work",
                name="Work",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.LINEAR,
                context="global",
            ),
        }
        workflow = WorkflowGraph(
            workflow_id="wf",
            nodes=list(stages.keys()),
            edges=[Edge(from_node_id="split", to_node_id="work")],
        )
        router = Router(workflow=workflow, stages=stages)
        task_manager = TaskManager()

        spec = TaskSpec(task_spec_id="test", request="do")
        task = task_manager.create_task(spec)

        # Invalid output (string)
        output = "not a valid split output"

        # Execute
        error = router._route_split(task, stages["split"], output, task_manager)

        # Verify error
        assert error is not None
        assert error.code == EngineErrorCode.ROUTING
        assert error.error_id == "invalid_split_output"

    def test_split_rejects_empty_subtask_inputs(self) -> None:
        """Test that _route_split rejects empty subtask_inputs."""
        stages = {
            "split": Node(
                stage_id="split",
                name="Split",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.SPLIT,
                context="global",
            ),
            "work": Node(
                stage_id="work",
                name="Work",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.LINEAR,
                context="global",
            ),
        }
        workflow = WorkflowGraph(
            workflow_id="wf",
            nodes=list(stages.keys()),
            edges=[Edge(from_node_id="split", to_node_id="work")],
        )
        router = Router(workflow=workflow, stages=stages)
        task_manager = TaskManager()

        spec = TaskSpec(task_spec_id="test", request="do")
        task = task_manager.create_task(spec)

        # Empty list
        output = {"subtask_inputs": []}

        # Execute
        error = router._route_split(task, stages["split"], output, task_manager)

        # Verify error
        assert error is not None
        assert error.code == EngineErrorCode.ROUTING
        assert error.error_id == "empty_subtask_inputs"

    def test_split_round_robin_to_multiple_edges(self) -> None:
        """Test that _route_split distributes subtasks across multiple edges."""
        stages = {
            "split": Node(
                stage_id="split",
                name="Split",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.SPLIT,
                context="global",
            ),
            "worker1": Node(
                stage_id="worker1",
                name="Worker 1",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.LINEAR,
                context="global",
            ),
            "worker2": Node(
                stage_id="worker2",
                name="Worker 2",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.LINEAR,
                context="global",
            ),
        }
        workflow = WorkflowGraph(
            workflow_id="wf",
            nodes=list(stages.keys()),
            edges=[
                Edge(from_node_id="split", to_node_id="worker1"),
                Edge(from_node_id="split", to_node_id="worker2"),
            ],
        )
        router = Router(workflow=workflow, stages=stages)
        task_manager = TaskManager()

        spec = TaskSpec(task_spec_id="test", request="do")
        task = task_manager.create_task(spec)

        # 4 subtasks -> round-robin across 2 edges
        output = {
            "subtask_inputs": [
                {"id": 1},
                {"id": 2},
                {"id": 3},
                {"id": 4},
            ]
        }

        # Execute
        error = router._route_split(task, stages["split"], output, task_manager)

        # Verify no error
        assert error is None

        # Verify distribution
        subtasks = task_manager.get_children(task.task_id)
        assert len(subtasks) == 4

        # Check round-robin distribution
        worker1_targets = [
            st for st in subtasks if st.current_stage_id == "worker1"
        ]
        worker2_targets = [
            st for st in subtasks if st.current_stage_id == "worker2"
        ]
        assert len(worker1_targets) == 2
        assert len(worker2_targets) == 2

    def test_split_single_input_in_list(self) -> None:
        """Test _route_split with single input in list."""
        stages = {
            "split": Node(
                stage_id="split",
                name="Split",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.SPLIT,
                context="global",
            ),
            "work": Node(
                stage_id="work",
                name="Work",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.LINEAR,
                context="global",
            ),
        }
        workflow = WorkflowGraph(
            workflow_id="wf",
            nodes=list(stages.keys()),
            edges=[Edge(from_node_id="split", to_node_id="work")],
        )
        router = Router(workflow=workflow, stages=stages)
        task_manager = TaskManager()

        spec = TaskSpec(task_spec_id="test", request="do")
        task = task_manager.create_task(spec)

        # Single item in subtask_inputs list
        output = {"subtask_inputs": [{"single": "task"}]}

        # Execute
        error = router._route_split(task, stages["split"], output, task_manager)

        # Verify success
        assert error is None
        assert len(task.child_task_ids) == 1

    def test_split_preserves_subtask_input_values(self) -> None:
        """Test that subtask_input values are preserved in subtasks."""
        stages = {
            "split": Node(
                stage_id="split",
                name="Split",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.SPLIT,
                context="global",
            ),
            "work": Node(
                stage_id="work",
                name="Work",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.LINEAR,
                context="global",
            ),
        }
        workflow = WorkflowGraph(
            workflow_id="wf",
            nodes=list(stages.keys()),
            edges=[Edge(from_node_id="split", to_node_id="work")],
        )
        router = Router(workflow=workflow, stages=stages)
        task_manager = TaskManager()

        spec = TaskSpec(task_spec_id="test", request="do")
        task = task_manager.create_task(spec)

        inputs = [
            {"id": 1, "name": "first"},
            {"id": 2, "name": "second"},
        ]
        output = {"subtask_inputs": inputs}

        # Execute
        router._route_split(task, stages["split"], output, task_manager)

        # Verify inputs preserved in lineage metadata
        subtasks = task_manager.get_children(task.task_id)
        for i, subtask in enumerate(sorted(subtasks, key=lambda s: s.task_id)):
            assert (
                subtask.lineage_metadata.get("subtask_input")
                == inputs[i]
            )
