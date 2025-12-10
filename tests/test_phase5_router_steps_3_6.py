"""Phase 5 Tests: Router v1.0 Steps 3-6 Implementation.

Tests for Steps 3-6 implementation:
- Step 3: _select_start_node - Select start node (default or explicit)
- Step 4: _enqueue_work / _process_worklist - FIFO worklist management
- Step 5: _route_start / _route_linear - Route from START and LINEAR nodes
- Step 6: _route_decision / _extract_selected_edge - Decision routing and edge extraction

Per AGENT_ENGINE_SPEC §3.1 and AGENT_ENGINE_OVERVIEW §3.2.
"""

import pytest
from agent_engine.exceptions import EngineError
from agent_engine.runtime.router import Router
from agent_engine.runtime.task_manager import TaskManager
from agent_engine.schemas import (
    Edge,
    Node,
    NodeKind,
    NodeRole,
    TaskMode,
    TaskSpec,
    UniversalStatus,
    WorkflowGraph,
)


class TestSelectStartNode:
    """Tests for Router._select_start_node method (Step 3)."""

    def test_select_default_start_node(self) -> None:
        """Test selecting the default start node when no explicit start provided."""
        stages = {
            "start1": Node(
                stage_id="start1",
                name="Start 1",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.START,
                default_start=True,
                context="global",
            ),
            "start2": Node(
                stage_id="start2",
                name="Start 2",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.START,
                default_start=False,
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
                Edge(from_node_id="start1", to_node_id="exit"),
                Edge(from_node_id="start2", to_node_id="exit"),
            ],
        )
        router = Router(workflow=workflow, stages=stages)

        # Execute
        node = router._select_start_node(start_node_id=None)

        # Verify
        assert node.stage_id == "start1"
        assert node.default_start is True

    def test_select_explicit_start_node(self) -> None:
        """Test selecting an explicitly provided start node."""
        stages = {
            "start1": Node(
                stage_id="start1",
                name="Start 1",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.START,
                default_start=True,
                context="global",
            ),
            "start2": Node(
                stage_id="start2",
                name="Start 2",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.START,
                default_start=False,
                context="global",
            ),
        }
        workflow = WorkflowGraph(
            workflow_id="wf",
            nodes=list(stages.keys()),
            edges=[],
        )
        router = Router(workflow=workflow, stages=stages)

        # Execute
        node = router._select_start_node(start_node_id="start2")

        # Verify
        assert node.stage_id == "start2"
        assert node.default_start is False

    def test_reject_invalid_explicit_start_node(self) -> None:
        """Test error when explicit start node ID is not found."""
        stages = {
            "start": Node(
                stage_id="start",
                name="Start",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.START,
                default_start=True,
                context="global",
            ),
        }
        workflow = WorkflowGraph(
            workflow_id="wf",
            nodes=list(stages.keys()),
            edges=[],
        )
        router = Router(workflow=workflow, stages=stages)

        # Execute & Verify
        with pytest.raises(EngineError) as exc_info:
            router._select_start_node(start_node_id="nonexistent")

        assert "not found in workflow" in str(exc_info.value)
        assert True

    def test_reject_non_start_explicit_node(self) -> None:
        """Test error when explicit start node is not a START role."""
        stages = {
            "start": Node(
                stage_id="start",
                name="Start",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.START,
                default_start=True,
                context="global",
            ),
            "linear": Node(
                stage_id="linear",
                name="Linear",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.LINEAR,
                context="global",
            ),
        }
        workflow = WorkflowGraph(
            workflow_id="wf",
            nodes=list(stages.keys()),
            edges=[Edge(from_node_id="start", to_node_id="linear")],
        )
        router = Router(workflow=workflow, stages=stages)

        # Execute & Verify
        with pytest.raises(EngineError) as exc_info:
            router._select_start_node(start_node_id="linear")

        assert "expected" in str(exc_info.value).lower()

    def test_no_default_start_node_error(self) -> None:
        """Test error when no default start node exists."""
        stages = {
            "start1": Node(
                stage_id="start1",
                name="Start 1",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.START,
                default_start=False,
                context="global",
            ),
            "start2": Node(
                stage_id="start2",
                name="Start 2",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.START,
                default_start=False,
                context="global",
            ),
        }
        workflow = WorkflowGraph(
            workflow_id="wf",
            nodes=list(stages.keys()),
            edges=[],
        )
        router = Router(workflow=workflow, stages=stages)

        # Execute & Verify
        with pytest.raises(EngineError) as exc_info:
            router._select_start_node(start_node_id=None)

        assert "No default start node" in str(exc_info.value)


class TestWorklistManagement:
    """Tests for Router._enqueue_work and _process_worklist methods (Step 4)."""

    def test_enqueue_work_adds_to_queue(self) -> None:
        """Test that _enqueue_work adds items to the worklist."""
        stages = {}
        workflow = WorkflowGraph(workflow_id="wf", nodes=[], edges=[])
        router = Router(workflow=workflow, stages=stages)

        # Execute
        router._enqueue_work("task1", "node1")
        router._enqueue_work("task2", "node2")

        # Verify
        assert len(router.task_queue) == 2

    def test_process_worklist_fifo_order(self) -> None:
        """Test that _process_worklist returns items in FIFO order."""
        stages = {}
        workflow = WorkflowGraph(workflow_id="wf", nodes=[], edges=[])
        router = Router(workflow=workflow, stages=stages)

        # Enqueue items
        router._enqueue_work("task1", "node1")
        router._enqueue_work("task2", "node2")
        router._enqueue_work("task3", "node3")

        # Process in FIFO order
        result1 = router._process_worklist()
        result2 = router._process_worklist()
        result3 = router._process_worklist()

        # Verify FIFO
        assert result1 == ("task1", "node1")
        assert result2 == ("task2", "node2")
        assert result3 == ("task3", "node3")

    def test_process_empty_worklist(self) -> None:
        """Test that _process_worklist returns None when empty."""
        stages = {}
        workflow = WorkflowGraph(workflow_id="wf", nodes=[], edges=[])
        router = Router(workflow=workflow, stages=stages)

        # Execute
        result = router._process_worklist()

        # Verify
        assert result is None

    def test_process_worklist_after_enqueue_dequeue_cycle(self) -> None:
        """Test enqueue and dequeue cycles work correctly."""
        stages = {}
        workflow = WorkflowGraph(workflow_id="wf", nodes=[], edges=[])
        router = Router(workflow=workflow, stages=stages)

        # Add and remove items
        router._enqueue_work("task1", "node1")
        assert router._process_worklist() == ("task1", "node1")

        # Queue should be empty
        assert router._process_worklist() is None

        # Add more items
        router._enqueue_work("task2", "node2")
        router._enqueue_work("task3", "node3")

        assert router._process_worklist() == ("task2", "node2")
        assert router._process_worklist() == ("task3", "node3")
        assert router._process_worklist() is None


class TestRouteStart:
    """Tests for Router._route_start method (Step 5a)."""

    def test_route_start_single_outbound_edge(self) -> None:
        """Test _route_start returns next node ID from single outbound edge."""
        stages = {
            "start": Node(
                stage_id="start",
                name="Start",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.START,
                default_start=True,
                context="global",
            ),
            "linear": Node(
                stage_id="linear",
                name="Linear",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.LINEAR,
                context="global",
            ),
        }
        workflow = WorkflowGraph(
            workflow_id="wf",
            nodes=list(stages.keys()),
            edges=[Edge(from_node_id="start", to_node_id="linear")],
        )
        router = Router(workflow=workflow, stages=stages)
        task_manager = TaskManager()

        spec = TaskSpec(task_spec_id="test", request="do")
        task = task_manager.create_task(spec)

        # Execute
        next_node_id = router._route_start(task, stages["start"])

        # Verify
        assert next_node_id == "linear"

    def test_route_start_no_outbound_edge_error(self) -> None:
        """Test _route_start error when no outbound edge exists."""
        stages = {
            "start": Node(
                stage_id="start",
                name="Start",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.START,
                default_start=True,
                context="global",
            ),
        }
        workflow = WorkflowGraph(
            workflow_id="wf",
            nodes=list(stages.keys()),
            edges=[],
        )
        router = Router(workflow=workflow, stages=stages)
        task_manager = TaskManager()

        spec = TaskSpec(task_spec_id="test", request="do")
        task = task_manager.create_task(spec)

        # Execute & Verify
        with pytest.raises(EngineError) as exc_info:
            router._route_start(task, stages["start"])

        assert "no outbound edge" in str(exc_info.value)
        assert True

    def test_route_start_multiple_edges_error(self) -> None:
        """Test _route_start error when multiple outbound edges exist."""
        stages = {
            "start": Node(
                stage_id="start",
                name="Start",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.START,
                default_start=True,
                context="global",
            ),
            "linear1": Node(
                stage_id="linear1",
                name="Linear 1",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.LINEAR,
                context="global",
            ),
            "linear2": Node(
                stage_id="linear2",
                name="Linear 2",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.LINEAR,
                context="global",
            ),
        }
        workflow = WorkflowGraph(
            workflow_id="wf",
            nodes=list(stages.keys()),
            edges=[
                Edge(from_node_id="start", to_node_id="linear1"),
                Edge(from_node_id="start", to_node_id="linear2"),
            ],
        )
        router = Router(workflow=workflow, stages=stages)
        task_manager = TaskManager()

        spec = TaskSpec(task_spec_id="test", request="do")
        task = task_manager.create_task(spec)

        # Execute & Verify
        with pytest.raises(EngineError) as exc_info:
            router._route_start(task, stages["start"])

        assert "outbound edges" in str(exc_info.value)
        assert True

    def test_route_start_invalid_target_node_error(self) -> None:
        """Test _route_start error when target node doesn't exist."""
        stages = {
            "start": Node(
                stage_id="start",
                name="Start",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.START,
                default_start=True,
                context="global",
            ),
        }
        workflow = WorkflowGraph(
            workflow_id="wf",
            nodes=["start"],
            edges=[Edge(from_node_id="start", to_node_id="nonexistent")],
        )
        router = Router(workflow=workflow, stages=stages)
        task_manager = TaskManager()

        spec = TaskSpec(task_spec_id="test", request="do")
        task = task_manager.create_task(spec)

        # Execute & Verify
        with pytest.raises(EngineError) as exc_info:
            router._route_start(task, stages["start"])

        assert "invalid target node" in str(exc_info.value)
        assert "invalid target node" in str(exc_info.value)


class TestRouteLinear:
    """Tests for Router._route_linear method (Step 5b)."""

    def test_route_linear_single_outbound_edge(self) -> None:
        """Test _route_linear returns next node ID from single outbound edge."""
        stages = {
            "linear1": Node(
                stage_id="linear1",
                name="Linear 1",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.LINEAR,
                context="global",
            ),
            "linear2": Node(
                stage_id="linear2",
                name="Linear 2",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.LINEAR,
                context="global",
            ),
        }
        workflow = WorkflowGraph(
            workflow_id="wf",
            nodes=list(stages.keys()),
            edges=[Edge(from_node_id="linear1", to_node_id="linear2")],
        )
        router = Router(workflow=workflow, stages=stages)
        task_manager = TaskManager()

        spec = TaskSpec(task_spec_id="test", request="do")
        task = task_manager.create_task(spec)

        # Execute
        next_node_id = router._route_linear(task, stages["linear1"])

        # Verify
        assert next_node_id == "linear2"

    def test_route_linear_no_outbound_edge_error(self) -> None:
        """Test _route_linear error when no outbound edge exists."""
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
            workflow_id="wf",
            nodes=list(stages.keys()),
            edges=[],
        )
        router = Router(workflow=workflow, stages=stages)
        task_manager = TaskManager()

        spec = TaskSpec(task_spec_id="test", request="do")
        task = task_manager.create_task(spec)

        # Execute & Verify
        with pytest.raises(EngineError) as exc_info:
            router._route_linear(task, stages["linear"])

        assert "no outbound edge" in str(exc_info.value)

    def test_route_linear_multiple_edges_error(self) -> None:
        """Test _route_linear error when multiple outbound edges exist."""
        stages = {
            "linear1": Node(
                stage_id="linear1",
                name="Linear 1",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.LINEAR,
                context="global",
            ),
            "linear2": Node(
                stage_id="linear2",
                name="Linear 2",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.LINEAR,
                context="global",
            ),
            "linear3": Node(
                stage_id="linear3",
                name="Linear 3",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.LINEAR,
                context="global",
            ),
        }
        workflow = WorkflowGraph(
            workflow_id="wf",
            nodes=list(stages.keys()),
            edges=[
                Edge(from_node_id="linear1", to_node_id="linear2"),
                Edge(from_node_id="linear1", to_node_id="linear3"),
            ],
        )
        router = Router(workflow=workflow, stages=stages)
        task_manager = TaskManager()

        spec = TaskSpec(task_spec_id="test", request="do")
        task = task_manager.create_task(spec)

        # Execute & Verify
        with pytest.raises(EngineError) as exc_info:
            router._route_linear(task, stages["linear1"])

        assert "outbound edges" in str(exc_info.value)


class TestRouteDecision:
    """Tests for Router._route_decision method (Step 6a)."""

    def test_route_decision_match_condition(self) -> None:
        """Test _route_decision selects edge matching selected_edge key."""
        stages = {
            "decision": Node(
                stage_id="decision",
                name="Decision",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.DECISION,
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
                Edge(from_node_id="decision", to_node_id="path1", condition="path_a"),
                Edge(from_node_id="decision", to_node_id="path2", condition="path_b"),
            ],
        )
        router = Router(workflow=workflow, stages=stages)
        task_manager = TaskManager()

        spec = TaskSpec(task_spec_id="test", request="do")
        task = task_manager.create_task(spec)

        # Execute
        output = {"selected_edge": "path_b"}
        next_node_id = router._route_decision(task, stages["decision"], output)

        # Verify
        assert next_node_id == "path2"

    def test_route_decision_match_condition_key(self) -> None:
        """Test _route_decision matches 'condition' key as secondary."""
        stages = {
            "decision": Node(
                stage_id="decision",
                name="Decision",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.DECISION,
                context="global",
            ),
            "yes": Node(
                stage_id="yes",
                name="Yes",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.LINEAR,
                context="global",
            ),
            "no": Node(
                stage_id="no",
                name="No",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.LINEAR,
                context="global",
            ),
        }
        workflow = WorkflowGraph(
            workflow_id="wf",
            nodes=list(stages.keys()),
            edges=[
                Edge(from_node_id="decision", to_node_id="yes", condition="yes"),
                Edge(from_node_id="decision", to_node_id="no", condition="no"),
            ],
        )
        router = Router(workflow=workflow, stages=stages)
        task_manager = TaskManager()

        spec = TaskSpec(task_spec_id="test", request="do")
        task = task_manager.create_task(spec)

        # Execute
        output = {"condition": "yes"}
        next_node_id = router._route_decision(task, stages["decision"], output)

        # Verify
        assert next_node_id == "yes"

    def test_route_decision_no_matching_edge_error(self) -> None:
        """Test _route_decision error when no edge matches selected condition."""
        stages = {
            "decision": Node(
                stage_id="decision",
                name="Decision",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.DECISION,
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
                Edge(from_node_id="decision", to_node_id="path1", condition="a"),
                Edge(from_node_id="decision", to_node_id="path2", condition="b"),
            ],
        )
        router = Router(workflow=workflow, stages=stages)
        task_manager = TaskManager()

        spec = TaskSpec(task_spec_id="test", request="do")
        task = task_manager.create_task(spec)

        # Execute & Verify
        output = {"selected_edge": "c"}
        with pytest.raises(EngineError) as exc_info:
            router._route_decision(task, stages["decision"], output)

        assert "does not match" in str(exc_info.value)
        assert True

    def test_route_decision_no_outbound_edges_error(self) -> None:
        """Test _route_decision error when no outbound edges exist."""
        stages = {
            "decision": Node(
                stage_id="decision",
                name="Decision",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.DECISION,
                context="global",
            ),
        }
        workflow = WorkflowGraph(
            workflow_id="wf",
            nodes=list(stages.keys()),
            edges=[],
        )
        router = Router(workflow=workflow, stages=stages)
        task_manager = TaskManager()

        spec = TaskSpec(task_spec_id="test", request="do")
        task = task_manager.create_task(spec)

        # Execute & Verify
        output = {"selected_edge": "any"}
        with pytest.raises(EngineError) as exc_info:
            router._route_decision(task, stages["decision"], output)

        assert "no outbound edges" in str(exc_info.value)

    def test_route_decision_insufficient_edges_error(self) -> None:
        """Test _route_decision error when only one outbound edge exists."""
        stages = {
            "decision": Node(
                stage_id="decision",
                name="Decision",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.DECISION,
                context="global",
            ),
            "path": Node(
                stage_id="path",
                name="Path",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.LINEAR,
                context="global",
            ),
        }
        workflow = WorkflowGraph(
            workflow_id="wf",
            nodes=list(stages.keys()),
            edges=[Edge(from_node_id="decision", to_node_id="path", condition="only")],
        )
        router = Router(workflow=workflow, stages=stages)
        task_manager = TaskManager()

        spec = TaskSpec(task_spec_id="test", request="do")
        task = task_manager.create_task(spec)

        # Execute & Verify
        output = {"selected_edge": "only"}
        with pytest.raises(EngineError) as exc_info:
            router._route_decision(task, stages["decision"], output)

        assert "outbound edges" in str(exc_info.value)


class TestExtractSelectedEdge:
    """Tests for Router._extract_selected_edge method (Step 6b)."""

    def test_extract_selected_edge_key_primary(self) -> None:
        """Test extraction from 'selected_edge' key (primary priority)."""
        stages = {}
        workflow = WorkflowGraph(workflow_id="wf", nodes=[], edges=[])
        router = Router(workflow=workflow, stages=stages)

        # Execute
        result = router._extract_selected_edge({"selected_edge": "path_a"})

        # Verify
        assert result == "path_a"

    def test_extract_condition_key_secondary(self) -> None:
        """Test extraction from 'condition' key (secondary priority)."""
        stages = {}
        workflow = WorkflowGraph(workflow_id="wf", nodes=[], edges=[])
        router = Router(workflow=workflow, stages=stages)

        # Execute
        result = router._extract_selected_edge({"condition": "route_b"})

        # Verify
        assert result == "route_b"

    def test_extract_route_key_tertiary(self) -> None:
        """Test extraction from 'route' key (tertiary priority)."""
        stages = {}
        workflow = WorkflowGraph(workflow_id="wf", nodes=[], edges=[])
        router = Router(workflow=workflow, stages=stages)

        # Execute
        result = router._extract_selected_edge({"route": "option_c"})

        # Verify
        assert result == "option_c"

    def test_extract_next_key_quaternary(self) -> None:
        """Test extraction from 'next' key (quaternary priority)."""
        stages = {}
        workflow = WorkflowGraph(workflow_id="wf", nodes=[], edges=[])
        router = Router(workflow=workflow, stages=stages)

        # Execute
        result = router._extract_selected_edge({"next": "stage_d"})

        # Verify
        assert result == "stage_d"

    def test_extract_priority_order(self) -> None:
        """Test that extraction follows priority order."""
        stages = {}
        workflow = WorkflowGraph(workflow_id="wf", nodes=[], edges=[])
        router = Router(workflow=workflow, stages=stages)

        # If all keys present, selected_edge takes priority
        output = {
            "selected_edge": "first",
            "condition": "second",
            "route": "third",
            "next": "fourth",
        }
        result = router._extract_selected_edge(output)
        assert result == "first"

        # If selected_edge absent, condition takes priority
        output = {
            "condition": "second",
            "route": "third",
            "next": "fourth",
        }
        result = router._extract_selected_edge(output)
        assert result == "second"

    def test_extract_string_output_directly(self) -> None:
        """Test that non-dict output is converted to string."""
        stages = {}
        workflow = WorkflowGraph(workflow_id="wf", nodes=[], edges=[])
        router = Router(workflow=workflow, stages=stages)

        # String output
        result = router._extract_selected_edge("simple_path")
        assert result == "simple_path"

        # Integer output
        result = router._extract_selected_edge(42)
        assert result == "42"

    def test_extract_none_output_error(self) -> None:
        """Test error when output is None."""
        stages = {}
        workflow = WorkflowGraph(workflow_id="wf", nodes=[], edges=[])
        router = Router(workflow=workflow, stages=stages)

        # Execute & Verify
        with pytest.raises(EngineError) as exc_info:
            router._extract_selected_edge(None)

        assert "None" in str(exc_info.value)

    def test_extract_empty_dict_error(self) -> None:
        """Test error when dict has no recognized keys."""
        stages = {}
        workflow = WorkflowGraph(workflow_id="wf", nodes=[], edges=[])
        router = Router(workflow=workflow, stages=stages)

        # Execute & Verify
        with pytest.raises(EngineError) as exc_info:
            router._extract_selected_edge({"unknown": "value"})

        assert "Cannot extract" in str(exc_info.value)
        assert True

    def test_extract_dict_with_none_values(self) -> None:
        """Test that dict with None values skips to next priority key."""
        stages = {}
        workflow = WorkflowGraph(workflow_id="wf", nodes=[], edges=[])
        router = Router(workflow=workflow, stages=stages)

        # selected_edge is None, should check condition next
        output = {
            "selected_edge": None,
            "condition": "valid_condition",
        }
        result = router._extract_selected_edge(output)
        assert result == "valid_condition"
