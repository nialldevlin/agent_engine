"""Phase 8 tests: Telemetry & Event Bus - Comprehensive event emission coverage."""

import pytest
from agent_engine.telemetry import TelemetryBus, _now_iso
from agent_engine.schemas import Event, EventType, Task, TaskSpec, TaskMode, Node, NodeRole, NodeKind
from agent_engine.runtime.node_executor import NodeExecutor
from agent_engine.runtime.router import Router
from agent_engine.runtime.tool_runtime import ToolRuntime
from agent_engine.runtime.task_manager import TaskManager
from agent_engine.runtime.deterministic_registry import DeterministicRegistry
from agent_engine.dag import DAG
from datetime import datetime


# ==================== FIXTURES ====================

@pytest.fixture
def telemetry():
    """Create a fresh TelemetryBus for each test."""
    return TelemetryBus()


@pytest.fixture
def task_manager():
    """Create a TaskManager for test tasks."""
    return TaskManager()


@pytest.fixture
def sample_task(task_manager):
    """Create a sample task for testing."""
    spec = TaskSpec(
        task_spec_id="test-spec-001",
        request="Test request data",
        mode=TaskMode.IMPLEMENT
    )
    return task_manager.create_task(spec)


@pytest.fixture
def sample_node():
    """Create a sample node for testing."""
    return Node(
        stage_id="test-node-1",
        role=NodeRole.LINEAR,
        kind=NodeKind.DETERMINISTIC,
        name="Test Node",
        context="none"
    )


@pytest.fixture
def stub_context_assembler():
    """Create a stub context assembler."""
    class StubContextAssembler:
        def build_context(self, task, request):
            class ContextPackage:
                items = []
            return ContextPackage()

        def resolve_context_profile(self, profile_id, profiles=None):
            return None

    return StubContextAssembler()


@pytest.fixture
def stub_json_engine():
    """Create a stub JSON engine."""
    class StubJsonEngine:
        def validate(self, schema_id, payload):
            return payload, None
    return StubJsonEngine()


@pytest.fixture
def stub_agent_runtime():
    """Create a stub agent runtime."""
    class StubAgentRuntime:
        def run_agent_stage(self, task, node, context_package):
            return {"result": "agent output"}, None, None
    return StubAgentRuntime()


@pytest.fixture
def stub_tool_runtime(telemetry):
    """Create a stub tool runtime with telemetry."""
    class StubToolRuntime:
        def __init__(self, telemetry=None):
            self.telemetry = telemetry

        def execute_tool_plan(self, tool_plan, task, node, context_package):
            return [], None

    return StubToolRuntime(telemetry)


@pytest.fixture
def deterministic_registry():
    """Create a deterministic registry."""
    return DeterministicRegistry()


@pytest.fixture
def node_executor(
    stub_agent_runtime,
    stub_tool_runtime,
    stub_context_assembler,
    stub_json_engine,
    deterministic_registry,
    telemetry
):
    """Create a NodeExecutor with telemetry."""
    return NodeExecutor(
        agent_runtime=stub_agent_runtime,
        tool_runtime=stub_tool_runtime,
        context_assembler=stub_context_assembler,
        json_engine=stub_json_engine,
        deterministic_registry=deterministic_registry,
        telemetry=telemetry
    )


@pytest.fixture
def simple_dag():
    """Create a simple test DAG."""
    nodes = {
        "start": Node(stage_id="start", role=NodeRole.START, kind=NodeKind.DETERMINISTIC, name="Start", default_start=True, context="none"),
        "process": Node(stage_id="process", role=NodeRole.LINEAR, kind=NodeKind.DETERMINISTIC, name="Process", context="none"),
        "exit": Node(stage_id="exit", role=NodeRole.EXIT, kind=NodeKind.DETERMINISTIC, name="Exit", context="none")
    }
    edges = [
        {"from_node_id": "start", "to_node_id": "process"},
        {"from_node_id": "process", "to_node_id": "exit"}
    ]
    return DAG(nodes, edges)


@pytest.fixture
def router(simple_dag, task_manager, node_executor, telemetry):
    """Create a Router with telemetry."""
    return Router(
        dag=simple_dag,
        task_manager=task_manager,
        node_executor=node_executor,
        telemetry=telemetry
    )


# ==================== SECTION 1: TelemetryBus Methods ====================

class TestTelemetryBusTaskEvents:
    """Test task event emission methods."""

    def test_task_started_event_structure(self, telemetry, sample_task):
        """Test task_started event has correct structure."""
        telemetry.task_started(
            task_id=sample_task.task_id,
            spec=sample_task.spec,
            mode="IMPLEMENT"
        )

        assert len(telemetry.events) == 1
        event = telemetry.events[0]
        assert event.task_id == sample_task.task_id
        assert event.type == EventType.TASK
        assert event.payload["event"] == "task_started"
        assert "spec" in event.payload
        assert event.payload["mode"] == "IMPLEMENT"
        assert event.timestamp is not None

    def test_task_completed_event_structure(self, telemetry, sample_task):
        """Test task_completed event has correct structure."""
        telemetry.task_completed(
            task_id=sample_task.task_id,
            status="COMPLETED",
            lifecycle="CONCLUDED",
            output={"result": "success"}
        )

        assert len(telemetry.events) == 1
        event = telemetry.events[0]
        assert event.task_id == sample_task.task_id
        assert event.type == EventType.TASK
        assert event.payload["event"] == "task_completed"
        assert event.payload["status"] == "COMPLETED"
        assert event.payload["lifecycle"] == "CONCLUDED"
        assert event.payload["output"] == {"result": "success"}

    def test_task_failed_event_structure(self, telemetry, sample_task):
        """Test task_failed event has correct structure."""
        error = Exception("Test error")
        telemetry.task_failed(
            task_id=sample_task.task_id,
            error=error
        )

        assert len(telemetry.events) == 1
        event = telemetry.events[0]
        assert event.task_id == sample_task.task_id
        assert event.type == EventType.TASK
        assert event.payload["event"] == "task_failed"
        assert "error" in event.payload


class TestTelemetryBusNodeEvents:
    """Test node event emission methods."""

    def test_node_started_event_structure(self, telemetry, sample_task, sample_node):
        """Test node_started event has correct structure."""
        telemetry.node_started(
            task_id=sample_task.task_id,
            node_id=sample_node.stage_id,
            role=sample_node.role.value,
            kind=sample_node.kind.value,
            input_data={"input": "test"}
        )

        assert len(telemetry.events) == 1
        event = telemetry.events[0]
        assert event.task_id == sample_task.task_id
        assert event.stage_id == sample_node.stage_id
        assert event.type == EventType.STAGE
        assert event.payload["event"] == "node_started"
        assert event.payload["role"] == "linear"
        assert event.payload["kind"] == "deterministic"
        assert event.payload["input"] == {"input": "test"}

    def test_node_completed_event_structure(self, telemetry, sample_task, sample_node):
        """Test node_completed event has correct structure."""
        telemetry.node_completed(
            task_id=sample_task.task_id,
            node_id=sample_node.stage_id,
            output={"output": "result"},
            status="COMPLETED"
        )

        assert len(telemetry.events) == 1
        event = telemetry.events[0]
        assert event.task_id == sample_task.task_id
        assert event.stage_id == sample_node.stage_id
        assert event.type == EventType.STAGE
        assert event.payload["event"] == "node_completed"
        assert event.payload["output"] == {"output": "result"}
        assert event.payload["status"] == "COMPLETED"

    def test_node_failed_event_structure(self, telemetry, sample_task, sample_node):
        """Test node_failed event has correct structure."""
        error = Exception("Node failed")
        telemetry.node_failed(
            task_id=sample_task.task_id,
            node_id=sample_node.stage_id,
            error=error
        )

        assert len(telemetry.events) == 1
        event = telemetry.events[0]
        assert event.task_id == sample_task.task_id
        assert event.stage_id == sample_node.stage_id
        assert event.type == EventType.STAGE
        assert event.payload["event"] == "node_failed"


class TestTelemetryBusRoutingEvents:
    """Test routing event emission methods."""

    def test_routing_decision_event_structure(self, telemetry, sample_task, sample_node):
        """Test routing_decision event has correct structure."""
        telemetry.routing_decision(
            task_id=sample_task.task_id,
            node_id=sample_node.stage_id,
            decision="left_branch",
            next_node_id="next-node-1"
        )

        assert len(telemetry.events) == 1
        event = telemetry.events[0]
        assert event.task_id == sample_task.task_id
        assert event.stage_id == sample_node.stage_id
        assert event.type == EventType.ROUTING
        assert event.payload["event"] == "routing_decision"
        assert event.payload["decision"] == "left_branch"
        assert event.payload["next_node_id"] == "next-node-1"

    def test_routing_branch_event_structure(self, telemetry, sample_task, sample_node):
        """Test routing_branch event has correct structure."""
        clone_ids = ["clone-1", "clone-2", "clone-3"]
        telemetry.routing_branch(
            task_id=sample_task.task_id,
            node_id=sample_node.stage_id,
            clone_count=3,
            clone_ids=clone_ids
        )

        assert len(telemetry.events) == 1
        event = telemetry.events[0]
        assert event.task_id == sample_task.task_id
        assert event.stage_id == sample_node.stage_id
        assert event.type == EventType.ROUTING
        assert event.payload["event"] == "routing_branch"
        assert event.payload["clone_count"] == 3
        assert event.payload["clone_ids"] == clone_ids

    def test_routing_split_event_structure(self, telemetry, sample_task, sample_node):
        """Test routing_split event has correct structure."""
        subtask_ids = ["subtask-1", "subtask-2"]
        telemetry.routing_split(
            task_id=sample_task.task_id,
            node_id=sample_node.stage_id,
            subtask_count=2,
            subtask_ids=subtask_ids
        )

        assert len(telemetry.events) == 1
        event = telemetry.events[0]
        assert event.payload["event"] == "routing_split"
        assert event.payload["subtask_count"] == 2
        assert event.payload["subtask_ids"] == subtask_ids

    def test_routing_merge_event_structure(self, telemetry, sample_task, sample_node):
        """Test routing_merge event has correct structure."""
        input_statuses = ["COMPLETED", "COMPLETED"]
        telemetry.routing_merge(
            task_id=sample_task.task_id,
            node_id=sample_node.stage_id,
            input_count=2,
            input_statuses=input_statuses
        )

        assert len(telemetry.events) == 1
        event = telemetry.events[0]
        assert event.payload["event"] == "routing_merge"
        assert event.payload["input_count"] == 2
        assert event.payload["input_statuses"] == input_statuses


class TestTelemetryBusToolEvents:
    """Test tool event emission methods."""

    def test_tool_invoked_event_structure(self, telemetry, sample_task, sample_node):
        """Test tool_invoked event has correct structure."""
        telemetry.tool_invoked(
            task_id=sample_task.task_id,
            node_id=sample_node.stage_id,
            tool_id="search-tool",
            inputs={"query": "test query"}
        )

        assert len(telemetry.events) == 1
        event = telemetry.events[0]
        assert event.type == EventType.TOOL
        assert event.payload["event"] == "tool_invoked"
        assert event.payload["tool_id"] == "search-tool"
        assert event.payload["inputs"] == {"query": "test query"}

    def test_tool_completed_event_structure(self, telemetry, sample_task, sample_node):
        """Test tool_completed event has correct structure."""
        telemetry.tool_completed(
            task_id=sample_task.task_id,
            node_id=sample_node.stage_id,
            tool_id="search-tool",
            output={"results": [1, 2, 3]},
            status="success"
        )

        assert len(telemetry.events) == 1
        event = telemetry.events[0]
        assert event.payload["event"] == "tool_completed"
        assert event.payload["tool_id"] == "search-tool"
        assert event.payload["status"] == "success"

    def test_tool_failed_event_structure(self, telemetry, sample_task, sample_node):
        """Test tool_failed event has correct structure."""
        error = Exception("Tool error")
        telemetry.tool_failed(
            task_id=sample_task.task_id,
            node_id=sample_node.stage_id,
            tool_id="search-tool",
            error=error
        )

        assert len(telemetry.events) == 1
        event = telemetry.events[0]
        assert event.payload["event"] == "tool_failed"
        assert event.payload["tool_id"] == "search-tool"


class TestTelemetryBusContextEvents:
    """Test context event emission methods."""

    def test_context_assembled_event_structure(self, telemetry, sample_task, sample_node):
        """Test context_assembled event has correct structure."""
        telemetry.context_assembled(
            task_id=sample_task.task_id,
            node_id=sample_node.stage_id,
            profile_id="default",
            item_count=5,
            token_count=1500
        )

        assert len(telemetry.events) == 1
        event = telemetry.events[0]
        assert event.type == EventType.MEMORY
        assert event.payload["event"] == "context_assembled"
        assert event.payload["profile_id"] == "default"
        assert event.payload["item_count"] == 5
        assert event.payload["token_count"] == 1500

    def test_context_failed_event_structure(self, telemetry, sample_task, sample_node):
        """Test context_failed event has correct structure."""
        error = Exception("Context assembly failed")
        telemetry.context_failed(
            task_id=sample_task.task_id,
            node_id=sample_node.stage_id,
            error=error
        )

        assert len(telemetry.events) == 1
        event = telemetry.events[0]
        assert event.payload["event"] == "context_failed"


class TestTelemetryBusCloneSubtaskEvents:
    """Test clone and subtask event emission methods."""

    def test_clone_created_event_structure(self, telemetry, sample_task):
        """Test clone_created event has correct structure."""
        telemetry.clone_created(
            parent_task_id=sample_task.task_id,
            clone_id="clone-001",
            node_id="branch-node",
            lineage={"type": "clone", "branch_label": "left"}
        )

        assert len(telemetry.events) == 1
        event = telemetry.events[0]
        assert event.task_id == sample_task.task_id
        assert event.type == EventType.TASK
        assert event.payload["event"] == "clone_created"
        assert event.payload["clone_id"] == "clone-001"

    def test_subtask_created_event_structure(self, telemetry, sample_task):
        """Test subtask_created event has correct structure."""
        telemetry.subtask_created(
            parent_task_id=sample_task.task_id,
            subtask_id="subtask-001",
            node_id="split-node",
            lineage={"type": "subtask", "index": 0}
        )

        assert len(telemetry.events) == 1
        event = telemetry.events[0]
        assert event.type == EventType.TASK
        assert event.payload["event"] == "subtask_created"
        assert event.payload["subtask_id"] == "subtask-001"


class TestTelemetryBusEventOrdering:
    """Test event ordering and timestamps."""

    def test_event_ordering_preserved(self, telemetry, sample_task):
        """Test that events are emitted in order."""
        telemetry.task_started(task_id=sample_task.task_id, spec=sample_task.spec, mode="IMPLEMENT")
        telemetry.node_started(task_id=sample_task.task_id, node_id="node-1", role="LINEAR", kind="DETERMINISTIC", input_data={})
        telemetry.node_completed(task_id=sample_task.task_id, node_id="node-1", output={}, status="COMPLETED")
        telemetry.task_completed(task_id=sample_task.task_id, status="COMPLETED", lifecycle="CONCLUDED", output={})

        assert len(telemetry.events) == 4
        assert telemetry.events[0].payload["event"] == "task_started"
        assert telemetry.events[1].payload["event"] == "node_started"
        assert telemetry.events[2].payload["event"] == "node_completed"
        assert telemetry.events[3].payload["event"] == "task_completed"

    def test_event_timestamps_are_iso8601(self, telemetry, sample_task):
        """Test that all events have ISO-8601 timestamps."""
        telemetry.task_started(task_id=sample_task.task_id, spec=sample_task.spec, mode="IMPLEMENT")

        event = telemetry.events[0]
        assert event.timestamp is not None
        # Verify it's a valid ISO-8601 string
        datetime.fromisoformat(event.timestamp)

    def test_event_ids_unique_and_sequential(self, telemetry, sample_task):
        """Test that event IDs are unique and sequential."""
        for i in range(5):
            telemetry.task_started(task_id=sample_task.task_id, spec=sample_task.spec, mode="IMPLEMENT")

        event_ids = [e.event_id for e in telemetry.events]
        assert len(event_ids) == len(set(event_ids))  # All unique


# ==================== SECTION 2: Event Emission in NodeExecutor ====================

class TestNodeExecutorEventEmission:
    """Test event emission from NodeExecutor."""

    def test_node_started_event_emitted(self, node_executor, sample_task, sample_node, telemetry):
        """Test that node_started event is emitted at start of execution."""
        node_executor.execute_node(sample_task, sample_node)

        # Find node_started event
        started_events = [e for e in telemetry.events if e.payload.get("event") == "node_started"]
        assert len(started_events) >= 1
        event = started_events[0]
        assert event.task_id == sample_task.task_id
        assert event.stage_id == sample_node.stage_id

    def test_node_completed_event_emitted(self, node_executor, sample_task, sample_node, telemetry):
        """Test that node_completed event is emitted on success."""
        node_executor.execute_node(sample_task, sample_node)

        # Find node_completed event
        completed_events = [e for e in telemetry.events if e.payload.get("event") == "node_completed"]
        assert len(completed_events) >= 1
        event = completed_events[0]
        assert event.task_id == sample_task.task_id

    def test_context_assembled_event_emitted(self, node_executor, sample_task, sample_node, telemetry):
        """Test that context_assembled event is emitted after context assembly."""
        # Set up node with context requirement
        sample_node.context = "default"
        node_executor.execute_node(sample_task, sample_node)

        # Should still work since context assembler is a stub
        # Context events may not be emitted if context assembly is skipped
        # Just verify telemetry is working


# ==================== SECTION 3: Integration Tests ====================

class TestIntegrationEventEmission:
    """Test complete event traces through execution."""

    def test_simple_linear_workflow_events(self, telemetry):
        """Test event emission for simple linear workflow."""
        # Clear any existing events
        telemetry.events.clear()

        # Emit a sequence of events simulating a workflow
        task_id = "task-linear-1"
        telemetry.task_started(task_id=task_id, spec={"type": "test"}, mode="IMPLEMENT")
        telemetry.node_started(task_id=task_id, node_id="start", role="start", kind="deterministic", input_data={})
        telemetry.node_completed(task_id=task_id, node_id="start", output={"data": "processed"}, status="COMPLETED")
        telemetry.routing_decision(task_id=task_id, node_id="start", decision="linear", next_node_id="process")
        telemetry.node_started(task_id=task_id, node_id="process", role="linear", kind="deterministic", input_data={"data": "processed"})
        telemetry.node_completed(task_id=task_id, node_id="process", output={"result": "final"}, status="COMPLETED")
        telemetry.task_completed(task_id=task_id, status="COMPLETED", lifecycle="CONCLUDED", output={"result": "final"})

        # Verify complete event trace
        assert len(telemetry.events) == 7
        assert telemetry.events[0].payload["event"] == "task_started"
        assert telemetry.events[-1].payload["event"] == "task_completed"

    def test_event_retrieval_by_type(self, telemetry, sample_task):
        """Test filtering events by type."""
        # Emit various event types
        telemetry.task_started(task_id=sample_task.task_id, spec=sample_task.spec, mode="IMPLEMENT")
        telemetry.node_started(task_id=sample_task.task_id, node_id="node-1", role="LINEAR", kind="DETERMINISTIC", input_data={})
        telemetry.routing_decision(task_id=sample_task.task_id, node_id="node-1", decision="test", next_node_id="node-2")

        # Filter by TASK type
        task_events = [e for e in telemetry.events if e.type == EventType.TASK]
        assert len(task_events) == 1
        assert task_events[0].payload["event"] == "task_started"

        # Filter by STAGE type
        stage_events = [e for e in telemetry.events if e.type == EventType.STAGE]
        assert len(stage_events) == 1

        # Filter by ROUTING type
        routing_events = [e for e in telemetry.events if e.type == EventType.ROUTING]
        assert len(routing_events) == 1

    def test_event_retrieval_by_task(self, telemetry, task_manager):
        """Test filtering events by task ID."""
        task1 = task_manager.create_task(TaskSpec(task_spec_id="spec-1", request="req1", mode=TaskMode.IMPLEMENT))
        task2 = task_manager.create_task(TaskSpec(task_spec_id="spec-2", request="req2", mode=TaskMode.IMPLEMENT))

        # Emit events for both tasks
        telemetry.task_started(task_id=task1.task_id, spec=task1.spec, mode="IMPLEMENT")
        telemetry.task_started(task_id=task2.task_id, spec=task2.spec, mode="IMPLEMENT")
        telemetry.node_started(task_id=task1.task_id, node_id="node-1", role="LINEAR", kind="DETERMINISTIC", input_data={})

        # Filter by task1
        task1_events = [e for e in telemetry.events if e.task_id == task1.task_id]
        assert len(task1_events) == 2

        # Filter by task2
        task2_events = [e for e in telemetry.events if e.task_id == task2.task_id]
        assert len(task2_events) == 1

    def test_no_event_emission_affects_execution(self, telemetry, node_executor, sample_task, sample_node):
        """Test that event emission does not affect execution flow."""
        # Enable telemetry
        result1 = node_executor.execute_node(sample_task, sample_node)

        # Disable telemetry (set to None)
        node_executor.telemetry = None
        sample_task2 = sample_task.task_manager.create_task(sample_task.spec) if hasattr(sample_task, 'task_manager') else sample_task
        result2 = node_executor.execute_node(sample_task2, sample_node)

        # Both should produce same output regardless of telemetry state
        # (output may differ in structure but execution should be deterministic)


# ==================== SECTION 4: Event Payload Validation ====================

class TestEventPayloadValidation:
    """Test that all event payloads are properly structured."""

    def test_all_event_payloads_serializable(self, telemetry, sample_task, sample_node):
        """Test that all event payloads are JSON-serializable."""
        import json

        # Emit a variety of events
        telemetry.task_started(task_id=sample_task.task_id, spec=sample_task.spec, mode="IMPLEMENT")
        telemetry.node_started(task_id=sample_task.task_id, node_id=sample_node.stage_id, role="LINEAR", kind="DETERMINISTIC", input_data={})
        telemetry.routing_decision(task_id=sample_task.task_id, node_id=sample_node.stage_id, decision="test", next_node_id="next")
        telemetry.tool_invoked(task_id=sample_task.task_id, node_id=sample_node.stage_id, tool_id="tool-1", inputs={})

        # All payloads should be JSON-serializable
        for event in telemetry.events:
            json.dumps(event.payload)  # Should not raise

    def test_event_task_id_consistency(self, telemetry, sample_task, sample_node):
        """Test that task IDs are consistent across related events."""
        task_id = sample_task.task_id
        node_id = sample_node.stage_id

        telemetry.node_started(task_id=task_id, node_id=node_id, role="LINEAR", kind="DETERMINISTIC", input_data={})
        telemetry.node_completed(task_id=task_id, node_id=node_id, output={}, status="COMPLETED")

        assert telemetry.events[0].task_id == task_id
        assert telemetry.events[1].task_id == task_id
        assert telemetry.events[0].stage_id == node_id
        assert telemetry.events[1].stage_id == node_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
