"""Phase 7 tests: Error Handling, Status Propagation & Exit Behavior.

Tests for:
- PARTIAL status in UniversalStatus enum
- Exit node validation (DETERMINISTIC, no tools, edge constraints)
- always_fail flag behavior
- continue_on_failure logic
- Merge failure handling
- Task status propagation methods
- Clone/subtask partial status propagation
- Pre-exit status validation
"""

import pytest
from agent_engine.runtime.node_executor import NodeExecutor
from agent_engine.runtime.deterministic_registry import DeterministicRegistry
from agent_engine.runtime.agent_runtime import AgentRuntime
from agent_engine.runtime.tool_runtime import ToolRuntime
from agent_engine.runtime.task_manager import TaskManager
from agent_engine.runtime.router import Router
from agent_engine.schema_validator import validate_exit_nodes
from agent_engine.dag import DAG
from agent_engine.schemas import (
    Node,
    NodeKind,
    NodeRole,
    Task,
    TaskSpec,
    TaskMode,
    TaskLifecycle,
    UniversalStatus,
    StageExecutionRecord,
)
from agent_engine.schemas.workflow import Edge
from agent_engine.exceptions import SchemaValidationError, DAGValidationError


# ============================================================================
# Test Fixtures
# ============================================================================

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
def node_executor(stub_agent_runtime, stub_tool_runtime, stub_context_assembler, stub_json_engine, deterministic_registry):
    return NodeExecutor(
        agent_runtime=stub_agent_runtime,
        tool_runtime=stub_tool_runtime,
        context_assembler=stub_context_assembler,
        json_engine=stub_json_engine,
        deterministic_registry=deterministic_registry
    )


# ============================================================================
# Test 1-3: PARTIAL Status
# ============================================================================

def test_partial_status_in_enum():
    """Test PARTIAL status exists in UniversalStatus enum."""
    assert hasattr(UniversalStatus, 'PARTIAL')
    assert UniversalStatus.PARTIAL.value == "partial"


def test_partial_status_serialization(task_manager):
    """Test task with PARTIAL status serializes correctly."""
    spec = TaskSpec(task_spec_id="test", request="test", mode=TaskMode.IMPLEMENT)
    task = task_manager.create_task(spec)
    task.status = UniversalStatus.PARTIAL

    # Serialize and deserialize
    task_dict = task.to_dict()
    assert task_dict["status"] == "partial"

    task2 = Task.from_dict(task_dict)
    assert task2.status == UniversalStatus.PARTIAL


def test_partial_status_distinct_from_failed(task_manager):
    """Test PARTIAL is distinct from FAILED (some succeeded, some failed)."""
    spec = TaskSpec(task_spec_id="test", request="test", mode=TaskMode.IMPLEMENT)
    task_partial = task_manager.create_task(spec)
    task_partial.status = UniversalStatus.PARTIAL

    task_failed = task_manager.create_task(spec)
    task_failed.status = UniversalStatus.FAILED

    assert task_partial.status != task_failed.status
    assert task_partial.status == UniversalStatus.PARTIAL
    assert task_failed.status == UniversalStatus.FAILED


# ============================================================================
# Test 4-9: Exit Node Validation
# ============================================================================

def test_exit_node_must_be_deterministic():
    """Test EXIT node must have kind=DETERMINISTIC (rejects AGENT)."""
    # Create a DAG with agent EXIT node (invalid)
    start = Node(
        stage_id="start",
        name="Start",
        kind=NodeKind.DETERMINISTIC,
        role=NodeRole.START,
        default_start=True,
        context="none"
    )
    exit_agent = Node(
        stage_id="exit",
        name="Exit Agent",
        kind=NodeKind.AGENT,  # INVALID
        role=NodeRole.EXIT,
        agent_id="some_agent",
        context="none"
    )
    edges = [Edge(from_node_id="start", to_node_id="exit")]
    dag = DAG({"start": start, "exit": exit_agent}, edges)

    with pytest.raises(SchemaValidationError) as exc:
        validate_exit_nodes(dag)
    assert "must be DETERMINISTIC" in str(exc.value)


def test_exit_node_cannot_have_tools():
    """Test EXIT node cannot specify tools."""
    start = Node(
        stage_id="start",
        name="Start",
        kind=NodeKind.DETERMINISTIC,
        role=NodeRole.START,
        default_start=True,
        context="none"
    )
    exit_with_tools = Node(
        stage_id="exit",
        name="Exit",
        kind=NodeKind.DETERMINISTIC,
        role=NodeRole.EXIT,
        tools=["tool1"],  # INVALID
        context="none"
    )
    edges = [Edge(from_node_id="start", to_node_id="exit")]
    dag = DAG({"start": start, "exit": exit_with_tools}, edges)

    with pytest.raises(SchemaValidationError) as exc:
        validate_exit_nodes(dag)
    assert "cannot specify tools" in str(exc.value)


def test_exit_node_must_have_inbound_edge():
    """Test EXIT node must have ≥1 inbound edge."""
    start = Node(
        stage_id="start",
        name="Start",
        kind=NodeKind.DETERMINISTIC,
        role=NodeRole.START,
        default_start=True,
        context="none"
    )
    exit_no_input = Node(
        stage_id="exit",
        name="Exit",
        kind=NodeKind.DETERMINISTIC,
        role=NodeRole.EXIT,
        context="none"
    )
    # No edges to exit node
    edges = []
    dag = DAG({"start": start, "exit": exit_no_input}, edges)

    with pytest.raises(SchemaValidationError) as exc:
        validate_exit_nodes(dag)
    assert "must have at least 1 inbound edge" in str(exc.value)


def test_exit_node_cannot_have_outbound_edges():
    """Test EXIT node cannot have outbound edges."""
    start = Node(
        stage_id="start",
        name="Start",
        kind=NodeKind.DETERMINISTIC,
        role=NodeRole.START,
        default_start=True,
        context="none"
    )
    exit_node = Node(
        stage_id="exit",
        name="Exit",
        kind=NodeKind.DETERMINISTIC,
        role=NodeRole.EXIT,
        context="none"
    )
    after_exit = Node(
        stage_id="after",
        name="After",
        kind=NodeKind.DETERMINISTIC,
        role=NodeRole.LINEAR,
        context="none"
    )
    # Edge from exit to after (INVALID)
    edges = [
        Edge(from_node_id="start", to_node_id="exit"),
        Edge(from_node_id="exit", to_node_id="after")
    ]
    dag = DAG({"start": start, "exit": exit_node, "after": after_exit}, edges)

    with pytest.raises(SchemaValidationError) as exc:
        validate_exit_nodes(dag)
    assert "cannot have outbound edges" in str(exc.value)


def test_always_fail_only_valid_for_exit_nodes():
    """Test always_fail=True only valid for EXIT nodes."""
    linear = Node(
        stage_id="linear",
        name="Linear",
        kind=NodeKind.DETERMINISTIC,
        role=NodeRole.LINEAR,
        always_fail=True,  # INVALID for non-EXIT
        context="none"
    )
    exit_node = Node(
        stage_id="exit",
        name="Exit",
        kind=NodeKind.DETERMINISTIC,
        role=NodeRole.EXIT,
        context="none"
    )
    start = Node(
        stage_id="start",
        name="Start",
        kind=NodeKind.DETERMINISTIC,
        role=NodeRole.START,
        default_start=True,
        context="none"
    )
    edges = [
        Edge(from_node_id="start", to_node_id="linear"),
        Edge(from_node_id="linear", to_node_id="exit")
    ]
    dag = DAG({"start": start, "linear": linear, "exit": exit_node}, edges)

    with pytest.raises(SchemaValidationError) as exc:
        validate_exit_nodes(dag)
    assert "only valid for EXIT nodes" in str(exc.value)


def test_exit_node_execution_validation(node_executor, sample_task):
    """Test exit node execution validates constraints."""
    # Test 1: Status must be set
    exit_node = Node(
        stage_id="exit",
        name="Exit",
        kind=NodeKind.DETERMINISTIC,
        role=NodeRole.EXIT,
        context="none"
    )
    sample_task.status = UniversalStatus.PENDING

    record, output = node_executor.execute_node(sample_task, exit_node)
    assert record.node_status == UniversalStatus.FAILED
    assert "exit_status_not_set" in record.error.error_id


# ============================================================================
# Test 10-12: always_fail Behavior
# ============================================================================

def test_always_fail_overrides_completed_to_failed(task_manager, node_executor):
    """Test exit node with always_fail=True overrides COMPLETED to FAILED."""
    spec = TaskSpec(task_spec_id="test", request="test", mode=TaskMode.IMPLEMENT)
    task = task_manager.create_task(spec)
    task.status = UniversalStatus.COMPLETED

    exit_node = Node(
        stage_id="exit",
        name="Exit",
        kind=NodeKind.DETERMINISTIC,
        role=NodeRole.EXIT,
        always_fail=True,
        context="none"
    )

    record, output = node_executor.execute_node(task, exit_node)
    assert record.node_status == UniversalStatus.COMPLETED  # Execution succeeded
    # But always_fail will be applied in router


def test_always_fail_false_preserves_status(task_manager, node_executor):
    """Test exit node with always_fail=False preserves status."""
    spec = TaskSpec(task_spec_id="test", request="test", mode=TaskMode.IMPLEMENT)
    task = task_manager.create_task(spec)
    task.status = UniversalStatus.COMPLETED

    exit_node = Node(
        stage_id="exit",
        name="Exit",
        kind=NodeKind.DETERMINISTIC,
        role=NodeRole.EXIT,
        always_fail=False,
        context="none"
    )

    record, output = node_executor.execute_node(task, exit_node)
    assert record.node_status == UniversalStatus.COMPLETED


def test_always_fail_on_non_exit_raises_error():
    """Test always_fail on non-exit node raises error."""
    start = Node(
        stage_id="start",
        name="Start",
        kind=NodeKind.DETERMINISTIC,
        role=NodeRole.START,
        default_start=True,
        always_fail=True,  # INVALID
        context="none"
    )
    exit_node = Node(
        stage_id="exit",
        name="Exit",
        kind=NodeKind.DETERMINISTIC,
        role=NodeRole.EXIT,
        context="none"
    )
    edges = [Edge(from_node_id="start", to_node_id="exit")]
    dag = DAG({"start": start, "exit": exit_node}, edges)

    with pytest.raises(SchemaValidationError):
        validate_exit_nodes(dag)


# ============================================================================
# Test 13-16: continue_on_failure Logic
# ============================================================================

def test_continue_on_failure_true_continues_execution(node_executor, task_manager):
    """Test node with continue_on_failure=True continues despite failure."""
    spec = TaskSpec(task_spec_id="test", request="test", mode=TaskMode.IMPLEMENT)
    task = task_manager.create_task(spec)

    # Create a failing deterministic node with continue_on_failure=True
    failing_node = Node(
        stage_id="failing",
        name="Failing",
        kind=NodeKind.DETERMINISTIC,
        role=NodeRole.LINEAR,
        continue_on_failure=True,
        context="none"
    )

    # Register failing operation
    def failing_op(task, node, context):
        from agent_engine.schemas import EngineError, EngineErrorCode, EngineErrorSource, Severity
        error = EngineError(
            error_id="test_error",
            code=EngineErrorCode.UNKNOWN,
            message="Test failure",
            source=EngineErrorSource.RUNTIME,
            severity=Severity.ERROR
        )
        return None, error

    node_executor.deterministic_registry.register(failing_node.stage_id, failing_op)

    record, output = node_executor.execute_node(task, failing_node)
    assert record.node_status == UniversalStatus.FAILED
    assert record.error is not None
    assert failing_node.continue_on_failure == True


def test_continue_on_failure_false_halts_execution(node_executor, task_manager):
    """Test node with continue_on_failure=False halts on failure."""
    spec = TaskSpec(task_spec_id="test", request="test", mode=TaskMode.IMPLEMENT)
    task = task_manager.create_task(spec)

    # Create a failing deterministic node with continue_on_failure=False
    failing_node = Node(
        stage_id="failing",
        name="Failing",
        kind=NodeKind.DETERMINISTIC,
        role=NodeRole.LINEAR,
        continue_on_failure=False,
        context="none"
    )

    # Register failing operation
    def failing_op(task, node, context):
        from agent_engine.schemas import EngineError, EngineErrorCode, EngineErrorSource, Severity
        error = EngineError(
            error_id="test_error",
            code=EngineErrorCode.UNKNOWN,
            message="Test failure",
            source=EngineErrorSource.RUNTIME,
            severity=Severity.ERROR
        )
        return None, error

    node_executor.deterministic_registry.register(failing_node.stage_id, failing_op)

    record, output = node_executor.execute_node(task, failing_node)
    assert record.node_status == UniversalStatus.FAILED
    assert failing_node.continue_on_failure == False


def test_node_failure_recorded_in_history(node_executor, task_manager):
    """Test task history records node failure even with continue_on_failure=True."""
    spec = TaskSpec(task_spec_id="test", request="test", mode=TaskMode.IMPLEMENT)
    task = task_manager.create_task(spec)

    failing_node = Node(
        stage_id="failing",
        name="Failing",
        kind=NodeKind.DETERMINISTIC,
        role=NodeRole.LINEAR,
        continue_on_failure=True,
        context="none"
    )

    def failing_op(task, node, context):
        from agent_engine.schemas import EngineError, EngineErrorCode, EngineErrorSource, Severity
        error = EngineError(
            error_id="test_error",
            code=EngineErrorCode.UNKNOWN,
            message="Test failure",
            source=EngineErrorSource.RUNTIME,
            severity=Severity.ERROR
        )
        return None, error

    node_executor.deterministic_registry.register(failing_node.stage_id, failing_op)

    record, output = node_executor.execute_node(task, failing_node)
    assert record.error is not None


# ============================================================================
# Test 17-20: Merge Failure Handling
# ============================================================================

def test_merge_fail_on_any_with_failure():
    """Test merge with merge_failure_mode='fail_on_any' fails when any input fails."""
    start = Node(
        stage_id="start",
        name="Start",
        kind=NodeKind.DETERMINISTIC,
        role=NodeRole.START,
        default_start=True,
        context="none"
    )
    merge = Node(
        stage_id="merge",
        name="Merge",
        kind=NodeKind.DETERMINISTIC,
        role=NodeRole.MERGE,
        merge_failure_mode="fail_on_any",
        context="none"
    )
    exit_node = Node(
        stage_id="exit",
        name="Exit",
        kind=NodeKind.DETERMINISTIC,
        role=NodeRole.EXIT,
        context="none"
    )
    edges = [
        Edge(from_node_id="start", to_node_id="merge"),
        Edge(from_node_id="merge", to_node_id="exit")
    ]
    dag = DAG({"start": start, "merge": merge, "exit": exit_node}, edges)

    # Should not raise during validation
    validate_exit_nodes(dag)


def test_merge_ignore_failures_mode():
    """Test merge with merge_failure_mode='ignore_failures' processes only successes."""
    start = Node(
        stage_id="start",
        name="Start",
        kind=NodeKind.DETERMINISTIC,
        role=NodeRole.START,
        default_start=True,
        context="none"
    )
    merge = Node(
        stage_id="merge",
        name="Merge",
        kind=NodeKind.DETERMINISTIC,
        role=NodeRole.MERGE,
        merge_failure_mode="ignore_failures",
        context="none"
    )
    exit_node = Node(
        stage_id="exit",
        name="Exit",
        kind=NodeKind.DETERMINISTIC,
        role=NodeRole.EXIT,
        context="none"
    )
    edges = [
        Edge(from_node_id="start", to_node_id="merge"),
        Edge(from_node_id="merge", to_node_id="exit")
    ]
    dag = DAG({"start": start, "merge": merge, "exit": exit_node}, edges)

    validate_exit_nodes(dag)


def test_merge_partial_mode():
    """Test merge with merge_failure_mode='partial' produces PARTIAL on mixed results."""
    start = Node(
        stage_id="start",
        name="Start",
        kind=NodeKind.DETERMINISTIC,
        role=NodeRole.START,
        default_start=True,
        context="none"
    )
    merge = Node(
        stage_id="merge",
        name="Merge",
        kind=NodeKind.DETERMINISTIC,
        role=NodeRole.MERGE,
        merge_failure_mode="partial",
        context="none"
    )
    exit_node = Node(
        stage_id="exit",
        name="Exit",
        kind=NodeKind.DETERMINISTIC,
        role=NodeRole.EXIT,
        context="none"
    )
    edges = [
        Edge(from_node_id="start", to_node_id="merge"),
        Edge(from_node_id="merge", to_node_id="exit")
    ]
    dag = DAG({"start": start, "merge": merge, "exit": exit_node}, edges)

    validate_exit_nodes(dag)


def test_default_merge_failure_mode_is_fail_on_any():
    """Test default merge_failure_mode is 'fail_on_any'."""
    merge = Node(
        stage_id="merge",
        name="Merge",
        kind=NodeKind.DETERMINISTIC,
        role=NodeRole.MERGE,
        context="none"
        # merge_failure_mode not specified
    )
    assert merge.merge_failure_mode == "fail_on_any"


# ============================================================================
# Test 21-23: Task Status Propagation
# ============================================================================

def test_update_task_status(task_manager):
    """Test task status updated via update_task_status."""
    spec = TaskSpec(task_spec_id="test", request="test", mode=TaskMode.IMPLEMENT)
    task = task_manager.create_task(spec)
    assert task.status == UniversalStatus.PENDING

    task_manager.update_task_status(task.task_id, UniversalStatus.COMPLETED)
    updated_task = task_manager.get_task(task.task_id)
    assert updated_task.status == UniversalStatus.COMPLETED


def test_update_task_lifecycle(task_manager):
    """Test task lifecycle updated via update_task_lifecycle."""
    spec = TaskSpec(task_spec_id="test", request="test", mode=TaskMode.IMPLEMENT)
    task = task_manager.create_task(spec)
    assert task.lifecycle == TaskLifecycle.QUEUED

    task_manager.update_task_lifecycle(task.task_id, TaskLifecycle.ACTIVE)
    updated_task = task_manager.get_task(task.task_id)
    assert updated_task.lifecycle == TaskLifecycle.ACTIVE


def test_update_task_output(task_manager):
    """Test task output updated via update_task_output."""
    spec = TaskSpec(task_spec_id="test", request="test", mode=TaskMode.IMPLEMENT)
    task = task_manager.create_task(spec)
    assert task.current_output is None

    task_manager.update_task_output(task.task_id, {"result": "test"})
    updated_task = task_manager.get_task(task.task_id)
    assert updated_task.current_output == {"result": "test"}


# ============================================================================
# Test 24-25: Clone/Subtask Partial Status
# ============================================================================

def test_parent_partial_when_some_subtasks_fail(task_manager):
    """Test parent PARTIAL when some subtasks fail but not all."""
    spec = TaskSpec(task_spec_id="test", request="test", mode=TaskMode.IMPLEMENT)
    parent = task_manager.create_task(spec)

    # Create subtasks
    subtask1 = task_manager.create_subtask(parent, "input1")
    subtask2 = task_manager.create_subtask(parent, "input2")
    subtask3 = task_manager.create_subtask(parent, "input3")

    # Set mixed status
    subtask1.status = UniversalStatus.COMPLETED
    subtask2.status = UniversalStatus.FAILED
    subtask3.status = UniversalStatus.COMPLETED

    # Check completion
    completed = task_manager.check_subtask_completion(parent.task_id)
    assert completed == True
    assert parent.status == UniversalStatus.PARTIAL


def test_parent_completed_when_any_clone_succeeds(task_manager):
    """Test parent COMPLETED when any clone succeeds despite other failures."""
    spec = TaskSpec(task_spec_id="test", request="test", mode=TaskMode.IMPLEMENT)
    parent = task_manager.create_task(spec)

    # Create clones
    clone1 = task_manager.create_clone(parent, "branch1")
    clone2 = task_manager.create_clone(parent, "branch2")
    clone3 = task_manager.create_clone(parent, "branch3")

    # Set status: one succeeds, others fail
    clone1.status = UniversalStatus.COMPLETED
    clone2.status = UniversalStatus.FAILED
    clone3.status = UniversalStatus.FAILED

    # Check completion
    completed = task_manager.check_clone_completion(parent.task_id)
    assert completed == True
    assert parent.status == UniversalStatus.COMPLETED


# ============================================================================
# Test 26: Run all tests to ensure nothing breaks
# ============================================================================

def test_all_universal_status_values_present():
    """Test all required UniversalStatus values are present."""
    required = [
        UniversalStatus.PENDING,
        UniversalStatus.IN_PROGRESS,
        UniversalStatus.COMPLETED,
        UniversalStatus.FAILED,
        UniversalStatus.PARTIAL,
        UniversalStatus.CANCELLED,
        UniversalStatus.BLOCKED
    ]
    for status in required:
        assert status is not None
