"""Phase 4 tests: Node execution skeleton and tool invocation."""

import pytest
from agent_engine.runtime.node_executor import NodeExecutor
from agent_engine.runtime.deterministic_registry import DeterministicRegistry
from agent_engine.runtime.agent_runtime import AgentRuntime
from agent_engine.runtime.tool_runtime import ToolRuntime
from agent_engine.runtime.task_manager import TaskManager
from agent_engine.schemas import (
    Node,
    NodeKind,
    NodeRole,
    Task,
    TaskSpec,
    TaskMode,
    UniversalStatus,
    StageExecutionRecord,
    ToolDefinition,
    ToolKind,
    ToolCallRecord,
)


# Test fixtures
@pytest.fixture
def task_manager():
    return TaskManager()


@pytest.fixture
def sample_task(task_manager):
    spec = TaskSpec(
        task_spec_id="test-spec",
        request="Test request",
        mode=TaskMode.IMPLEMENT
    )
    return task_manager.create_task(spec)


@pytest.fixture
def deterministic_registry():
    return DeterministicRegistry()


@pytest.fixture
def stub_context_assembler():
    class StubContextAssembler:
        def build_context(self, task, request):
            class ContextPackage:
                items = []
            return ContextPackage()

        def get_context_metadata(self, context_package):
            return {'items_count': 0}

    return StubContextAssembler()


@pytest.fixture
def stub_json_engine():
    class StubJsonEngine:
        def validate(self, schema_id, payload):
            return payload, None

    return StubJsonEngine()


@pytest.fixture
def stub_agent_runtime():
    class StubAgentRuntime:
        def run_agent_stage(self, task, node, context_package):
            return {"result": "agent output"}, None, None

    return StubAgentRuntime()


@pytest.fixture
def stub_tool_runtime():
    class StubToolRuntime:
        def execute_tool_plan(self, tool_plan, task, node, context_package):
            return [], None

    return StubToolRuntime()


@pytest.fixture
def node_executor(
    stub_agent_runtime,
    stub_tool_runtime,
    stub_context_assembler,
    stub_json_engine,
    deterministic_registry
):
    return NodeExecutor(
        agent_runtime=stub_agent_runtime,
        tool_runtime=stub_tool_runtime,
        context_assembler=stub_context_assembler,
        json_engine=stub_json_engine,
        deterministic_registry=deterministic_registry
    )


# Test classes

class TestStageExecutionRecordSchema:
    """Test extended StageExecutionRecord schema."""

    def test_record_has_all_required_fields(self):
        """Test that StageExecutionRecord has all Phase 4 fields."""
        record = StageExecutionRecord(
            node_id="test_node",
            node_role=NodeRole.LINEAR,
            node_kind=NodeKind.DETERMINISTIC,
            input={"input": "data"},
            output={"output": "data"},
            node_status=UniversalStatus.COMPLETED,
            context_profile_id="profile_1",
            started_at="2025-01-01T00:00:00Z",
            completed_at="2025-01-01T00:01:00Z"
        )

        assert record.node_id == "test_node"
        assert record.node_role == NodeRole.LINEAR
        assert record.node_kind == NodeKind.DETERMINISTIC
        assert record.input == {"input": "data"}
        assert record.output == {"output": "data"}
        assert record.node_status == UniversalStatus.COMPLETED
        assert record.context_profile_id == "profile_1"
        assert record.tool_plan is None
        assert record.tool_calls == []
        assert record.context_metadata == {}

    def test_record_with_tool_plan(self):
        """Test that StageExecutionRecord can hold tool_plan."""
        tool_plan = {"steps": [{"tool_id": "tool1", "inputs": {"x": 1}}]}
        record = StageExecutionRecord(
            node_id="test_node",
            node_role=NodeRole.LINEAR,
            node_kind=NodeKind.AGENT,
            tool_plan=tool_plan,
            node_status=UniversalStatus.COMPLETED,
        )

        assert record.tool_plan == tool_plan


class TestDeterministicRegistry:
    """Test DeterministicRegistry functionality."""

    def test_register_and_get_operation(self, deterministic_registry, sample_task):
        """Test registering and retrieving operations."""
        def custom_op(task, node, context):
            return {"custom": "output"}, None

        deterministic_registry.register("node_1", custom_op)
        retrieved = deterministic_registry.get("node_1")

        assert retrieved is not None
        assert retrieved == custom_op

    def test_get_nonexistent_operation(self, deterministic_registry):
        """Test getting operation that doesn't exist."""
        result = deterministic_registry.get("nonexistent")
        assert result is None

    def test_default_operations_registered(self, deterministic_registry):
        """Test that default operations are registered."""
        assert deterministic_registry.default_start is not None
        assert deterministic_registry.default_linear is not None
        assert deterministic_registry.default_decision is not None
        assert deterministic_registry.default_exit is not None

    def test_default_start_operation(self, deterministic_registry, sample_task):
        """Test default START operation."""
        node = Node(
            stage_id="start_1",
            name="Start",
            kind=NodeKind.DETERMINISTIC,
            role=NodeRole.START,
            context="none"
        )

        output, error = deterministic_registry.default_start(sample_task, node, None)
        assert error is None
        assert output is not None

    def test_default_linear_operation(self, deterministic_registry, sample_task):
        """Test default LINEAR operation (identity)."""
        sample_task.current_output = {"data": "test"}
        node = Node(
            stage_id="linear_1",
            name="Linear",
            kind=NodeKind.DETERMINISTIC,
            role=NodeRole.LINEAR,
            context="none"
        )

        output, error = deterministic_registry.default_linear(sample_task, node, None)
        assert error is None
        assert output == {"data": "test"}

    def test_default_decision_operation(self, deterministic_registry, sample_task):
        """Test default DECISION operation."""
        sample_task.current_output = {"decision": "branch_a"}
        node = Node(
            stage_id="decision_1",
            name="Decision",
            kind=NodeKind.DETERMINISTIC,
            role=NodeRole.DECISION,
            context="none"
        )

        output, error = deterministic_registry.default_decision(sample_task, node, None)
        assert error is None
        assert output == {"decision": "branch_a"}

    def test_get_default_for_role_start(self, deterministic_registry):
        """Test get_default_for_role returns correct operation for START."""
        op = deterministic_registry.get_default_for_role(NodeRole.START)
        assert op is not None
        assert op == deterministic_registry.default_start

    def test_get_default_for_role_linear(self, deterministic_registry):
        """Test get_default_for_role returns correct operation for LINEAR."""
        op = deterministic_registry.get_default_for_role(NodeRole.LINEAR)
        assert op is not None
        assert op == deterministic_registry.default_linear

    def test_get_default_for_role_decision(self, deterministic_registry):
        """Test get_default_for_role returns correct operation for DECISION."""
        op = deterministic_registry.get_default_for_role(NodeRole.DECISION)
        assert op is not None
        assert op == deterministic_registry.default_decision

    def test_get_default_for_role_exit(self, deterministic_registry):
        """Test get_default_for_role returns correct operation for EXIT."""
        op = deterministic_registry.get_default_for_role(NodeRole.EXIT)
        assert op is not None
        assert op == deterministic_registry.default_exit


class TestNodeExecutorDeterministic:
    """Test NodeExecutor with deterministic nodes."""

    def test_execute_deterministic_node_with_registry(
        self,
        node_executor,
        sample_task,
        deterministic_registry
    ):
        """Test deterministic node execution with registered operation."""
        # Register custom operation
        def custom_transform(task, node, context):
            return {"transformed": "data"}, None

        deterministic_registry.register("transform_node", custom_transform)

        node = Node(
            stage_id="transform_node",
            name="Transform",
            kind=NodeKind.DETERMINISTIC,
            role=NodeRole.LINEAR,
            context="none"
        )

        record, output = node_executor.execute_node(sample_task, node)

        assert record.node_status == UniversalStatus.COMPLETED
        assert output == {"transformed": "data"}
        assert record.output == {"transformed": "data"}

    def test_execute_deterministic_node_default(
        self,
        node_executor,
        sample_task
    ):
        """Test deterministic node execution with default operation."""
        sample_task.current_output = {"existing": "output"}

        node = Node(
            stage_id="linear_default",
            name="Linear Default",
            kind=NodeKind.DETERMINISTIC,
            role=NodeRole.LINEAR,
            context="none"
        )

        record, output = node_executor.execute_node(sample_task, node)

        assert record.node_status == UniversalStatus.COMPLETED
        assert output == {"existing": "output"}

    def test_execute_start_node(
        self,
        node_executor,
        sample_task
    ):
        """Test START node execution."""
        node = Node(
            stage_id="start_1",
            name="Start",
            kind=NodeKind.DETERMINISTIC,
            role=NodeRole.START,
            context="none"
        )

        record, output = node_executor.execute_node(sample_task, node)

        assert record.node_status == UniversalStatus.COMPLETED
        assert record.node_role == NodeRole.START
        assert record.node_kind == NodeKind.DETERMINISTIC

    def test_execute_exit_node(
        self,
        node_executor,
        sample_task
    ):
        """Test EXIT node execution (read-only)."""
        sample_task.current_output = {"final": "result"}

        node = Node(
            stage_id="exit_1",
            name="Exit",
            kind=NodeKind.DETERMINISTIC,
            role=NodeRole.EXIT,
            context="none"
        )

        record, output = node_executor.execute_node(sample_task, node)

        assert record.node_status == UniversalStatus.COMPLETED
        assert output == {"final": "result"}


class TestNodeExecutorAgent:
    """Test NodeExecutor with agent nodes."""

    def test_execute_agent_node_simple(
        self,
        node_executor,
        sample_task
    ):
        """Test simple agent node execution."""
        node = Node(
            stage_id="agent_1",
            name="Agent",
            kind=NodeKind.AGENT,
            role=NodeRole.LINEAR,
            agent_id="agent_a",
            context="global"
        )

        record, output = node_executor.execute_node(sample_task, node)

        assert record.node_status == UniversalStatus.COMPLETED
        assert record.node_kind == NodeKind.AGENT
        assert output is not None

    def test_execute_agent_node_with_tools(
        self,
        node_executor,
        sample_task
    ):
        """Test agent node with tools available."""
        node = Node(
            stage_id="agent_with_tools",
            name="Agent with Tools",
            kind=NodeKind.AGENT,
            role=NodeRole.LINEAR,
            agent_id="agent_b",
            context="global",
            tools=["tool1", "tool2"]
        )

        record, output = node_executor.execute_node(sample_task, node)

        assert record.node_status == UniversalStatus.COMPLETED
        assert record.node_kind == NodeKind.AGENT


class TestNodeExecutorHistory:
    """Test complete history recording."""

    def test_history_includes_node_metadata(
        self,
        node_executor,
        sample_task
    ):
        """Test that history includes node_id, role, kind."""
        node = Node(
            stage_id="test_node",
            name="Test",
            kind=NodeKind.DETERMINISTIC,
            role=NodeRole.LINEAR,
            context="none"
        )

        record, _ = node_executor.execute_node(sample_task, node)

        assert record.node_id == "test_node"
        assert record.node_role == NodeRole.LINEAR
        assert record.node_kind == NodeKind.DETERMINISTIC

    def test_history_includes_timestamps(
        self,
        node_executor,
        sample_task
    ):
        """Test that history includes timestamps."""
        node = Node(
            stage_id="test_node",
            name="Test",
            kind=NodeKind.DETERMINISTIC,
            role=NodeRole.LINEAR,
            context="none"
        )

        record, _ = node_executor.execute_node(sample_task, node)

        assert record.started_at is not None
        assert record.completed_at is not None

    def test_history_includes_context_metadata(
        self,
        node_executor,
        sample_task
    ):
        """Test that history includes context metadata."""
        node = Node(
            stage_id="test_node",
            name="Test",
            kind=NodeKind.DETERMINISTIC,
            role=NodeRole.LINEAR,
            context="none"
        )

        record, _ = node_executor.execute_node(sample_task, node)

        assert record.context_metadata is not None
        assert isinstance(record.context_metadata, dict)

    def test_history_includes_input_and_output(
        self,
        node_executor,
        sample_task
    ):
        """Test that history includes input and output."""
        sample_task.current_output = {"test": "input"}

        node = Node(
            stage_id="test_node",
            name="Test",
            kind=NodeKind.DETERMINISTIC,
            role=NodeRole.LINEAR,
            context="none"
        )

        record, output = node_executor.execute_node(sample_task, node)

        assert record.input == {"test": "input"}
        assert record.output == {"test": "input"}


class TestFailureHandling:
    """Test failure handling and error recording."""

    def test_execution_error_creates_error_record(
        self,
        node_executor,
        sample_task,
        deterministic_registry
    ):
        """Test that execution errors create error records."""
        # Register operation that fails
        def failing_op(task, node, context):
            raise ValueError("Operation failed")

        deterministic_registry.register("failing_node", failing_op)

        node = Node(
            stage_id="failing_node",
            name="Failing",
            kind=NodeKind.DETERMINISTIC,
            role=NodeRole.LINEAR,
            context="none"
        )

        record, output = node_executor.execute_node(sample_task, node)

        assert record.node_status == UniversalStatus.FAILED
        assert record.error is not None
        assert output is None

    def test_node_status_failed_on_error(
        self,
        node_executor,
        sample_task,
        deterministic_registry
    ):
        """Test that node_status is set to FAILED on error."""
        def failing_op(task, node, context):
            raise RuntimeError("Test error")

        deterministic_registry.register("error_node", failing_op)

        node = Node(
            stage_id="error_node",
            name="Error",
            kind=NodeKind.DETERMINISTIC,
            role=NodeRole.LINEAR,
            context="none"
        )

        record, _ = node_executor.execute_node(sample_task, node)

        assert record.node_status == UniversalStatus.FAILED


class TestContextAssembly:
    """Test context assembly and metadata."""

    def test_context_profile_recorded(
        self,
        node_executor,
        sample_task
    ):
        """Test that context profile is recorded in history."""
        node = Node(
            stage_id="test_node",
            name="Test",
            kind=NodeKind.DETERMINISTIC,
            role=NodeRole.LINEAR,
            context="profile_1"
        )

        record, _ = node_executor.execute_node(sample_task, node)

        assert record.context_profile_id == "profile_1"

    def test_global_context_recorded(
        self,
        node_executor,
        sample_task
    ):
        """Test that global context is recorded."""
        node = Node(
            stage_id="test_node",
            name="Test",
            kind=NodeKind.DETERMINISTIC,
            role=NodeRole.LINEAR,
            context="global"
        )

        record, _ = node_executor.execute_node(sample_task, node)

        assert record.context_profile_id == "global"


class TestNodeRoleHandling:
    """Test handling of different node roles."""

    def test_all_roles_supported(self, node_executor, sample_task):
        """Test that all node roles are supported."""
        roles = [
            NodeRole.START,
            NodeRole.LINEAR,
            NodeRole.DECISION,
            NodeRole.BRANCH,
            NodeRole.SPLIT,
            NodeRole.MERGE,
            NodeRole.EXIT,
        ]

        for role in roles:
            node = Node(
                stage_id=f"node_{role.value}",
                name=f"Node {role.value}",
                kind=NodeKind.DETERMINISTIC if role in [NodeRole.START, NodeRole.EXIT] else NodeKind.DETERMINISTIC,
                role=role,
                context="none"
            )

            record, _ = node_executor.execute_node(sample_task, node)
            assert record.node_role == role


class TestToolPlanEmission:
    """Test tool plan emission and handling."""

    def test_tool_plan_recorded_in_history(
        self,
        node_executor,
        sample_task
    ):
        """Test that tool plans are recorded in execution history."""
        # Create a custom agent runtime that emits tool plan
        class ToolPlanAgentRuntime:
            def run_agent_stage(self, task, node, context_package):
                tool_plan = {"steps": [{"tool_id": "tool1", "inputs": {"x": 1}}]}
                return "result", None, tool_plan

        node_executor.agent_runtime = ToolPlanAgentRuntime()

        node = Node(
            stage_id="agent_with_plan",
            name="Agent with Plan",
            kind=NodeKind.AGENT,
            role=NodeRole.LINEAR,
            agent_id="agent_c",
            context="global",
            tools=["tool1"]
        )

        record, _ = node_executor.execute_node(sample_task, node)

        assert record.tool_plan is not None
        assert "steps" in record.tool_plan


class TestRecordCreation:
    """Test StageExecutionRecord creation in NodeExecutor."""

    def test_record_has_correct_status_on_success(
        self,
        node_executor,
        sample_task
    ):
        """Test that successful execution sets COMPLETED status."""
        node = Node(
            stage_id="success_node",
            name="Success",
            kind=NodeKind.DETERMINISTIC,
            role=NodeRole.LINEAR,
            context="none"
        )

        record, _ = node_executor.execute_node(sample_task, node)

        assert record.node_status == UniversalStatus.COMPLETED

    def test_record_has_correct_status_on_failure(
        self,
        node_executor,
        sample_task,
        deterministic_registry
    ):
        """Test that failed execution sets FAILED status."""
        def failing_op(task, node, context):
            raise Exception("Test")

        deterministic_registry.register("fail_node", failing_op)

        node = Node(
            stage_id="fail_node",
            name="Fail",
            kind=NodeKind.DETERMINISTIC,
            role=NodeRole.LINEAR,
            context="none"
        )

        record, _ = node_executor.execute_node(sample_task, node)

        assert record.node_status == UniversalStatus.FAILED


class TestTaskOutputUpdate:
    """Test that task current_output is updated correctly."""

    def test_task_output_updated_on_success(
        self,
        node_executor,
        sample_task
    ):
        """Test that task current_output is updated after successful execution."""
        sample_task.current_output = {"prev": "output"}

        node = Node(
            stage_id="test_node",
            name="Test",
            kind=NodeKind.DETERMINISTIC,
            role=NodeRole.LINEAR,
            context="none"
        )

        _, output = node_executor.execute_node(sample_task, node)

        assert output == {"prev": "output"}

    def test_task_output_not_updated_on_failure(
        self,
        node_executor,
        sample_task,
        deterministic_registry
    ):
        """Test that task current_output is not updated after failed execution."""
        original_output = {"prev": "output"}
        sample_task.current_output = original_output

        def failing_op(task, node, context):
            raise Exception("Test")

        deterministic_registry.register("fail_node", failing_op)

        node = Node(
            stage_id="fail_node",
            name="Fail",
            kind=NodeKind.DETERMINISTIC,
            role=NodeRole.LINEAR,
            context="none"
        )

        _, output = node_executor.execute_node(sample_task, node)

        assert output is None
        assert sample_task.current_output == original_output


# Run with: python3 -m pytest tests/test_phase4_node_execution.py -v
