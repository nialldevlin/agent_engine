import pytest
from pydantic import ValidationError

from agent_engine.json_engine import validate
from agent_engine.schemas import (
    AgentDefinition,
    AgentRole,
    Edge,
    EngineError,
    EngineErrorCode,
    EngineErrorSource,
    FailureCode,
    FailureSignature,
    Node,
    NodeKind,
    NodeRole,
    Task,
    TaskLifecycle,
    TaskMode,
    TaskSpec,
    ToolDefinition,
    ToolKind,
    ToolRiskLevel,
    UniversalStatus,
    WorkflowGraph,
    get_schema_json,
)


def test_task_spec_and_task_instantiation() -> None:
    spec = TaskSpec(task_spec_id="spec-1", request="Fix bug", mode=TaskMode.ANALYSIS_ONLY)
    task = Task(task_id="task-1", spec=spec, task_memory_ref="task_mem", project_memory_ref="proj_mem", global_memory_ref="global_mem")
    assert task.status == UniversalStatus.PENDING
    assert task.spec.request == "Fix bug"


def test_task_invalid_missing_required() -> None:
    with pytest.raises(ValidationError):
        TaskSpec(request="missing id")  # type: ignore[arg-type]


def test_stage_and_workflow_graph() -> None:
    node = Node(stage_id="s1", name="do", kind=NodeKind.AGENT, role=NodeRole.START, default_start=True, context="global")
    graph = WorkflowGraph(workflow_id="wf1", nodes=[node.stage_id], edges=[])
    assert graph.workflow_id == "wf1"
    assert graph.nodes == ["s1"]


def test_tool_definition() -> None:
    tool = ToolDefinition(
        tool_id="t1",
        kind=ToolKind.DETERMINISTIC,
        name="ls",
        description="List files",
        inputs_schema_id="input-schema",
        outputs_schema_id="output-schema",
        risk_level=ToolRiskLevel.LOW,
    )
    assert tool.capabilities == []


def test_agent_definition_defaults() -> None:
    agent = AgentDefinition(agent_id="a1", role=AgentRole.AGENT)
    assert agent.manifest.tool_bias.value == "balanced"


def test_failure_and_error_models() -> None:
    failure = FailureSignature(code=FailureCode.JSON_ERROR, message="bad json")
    error = EngineError(
        error_id="e1",
        code=EngineErrorCode.JSON,
        message="invalid",
        source=EngineErrorSource.JSON_ENGINE,
    )
    assert failure.severity.value == "error"
    assert error.code == EngineErrorCode.JSON


def test_schema_registry_lookup() -> None:
    schema = get_schema_json("task_spec")
    assert schema["title"] == "TaskSpec"
    with pytest.raises(KeyError):
        get_schema_json("nonexistent")


def test_stage_round_trip_validation() -> None:
    node = Node(stage_id="s-linear", name="Linear", kind=NodeKind.DETERMINISTIC, role=NodeRole.LINEAR, context="global")
    payload = node.model_dump()
    restored, err = validate("node", payload)
    assert err is None
    assert restored.stage_id == node.stage_id


def test_workflow_round_trip_validation() -> None:
    graph = WorkflowGraph(
        workflow_id="wf2",
        nodes=["start", "end"],
        edges=[Edge(from_node_id="start", to_node_id="end")],
    )
    payload = graph.model_dump()
    restored, err = validate("workflow_graph", payload)
    assert err is None
    assert restored.workflow_id == "wf2"


def test_tool_plan_round_trip() -> None:
    """Test ToolPlan schema round-trip serialization."""
    from agent_engine.schemas import ToolPlan, ToolStep, ToolStepKind

    tool_plan = ToolPlan(
        tool_plan_id="tp-1",
        steps=[
            ToolStep(step_id="s1", tool_id="t1", inputs={"path": "/tmp/file.txt"}, kind=ToolStepKind.READ)
        ],
    )
    payload = tool_plan.model_dump()
    restored, err = validate("tool_plan", payload)
    assert err is None
    assert restored.tool_plan_id == "tp-1"
    assert len(restored.steps) == 1
    assert restored.steps[0].kind == ToolStepKind.READ


def test_override_spec_round_trip() -> None:
    """Test OverrideSpec schema round-trip serialization with payloads."""
    from agent_engine.schemas import OverrideKind, OverrideScope, OverrideSeverity, OverrideSpec

    override = OverrideSpec(
        override_id="override-1",
        kind=OverrideKind.SAFETY,
        scope=OverrideScope.TASK,
        severity=OverrideSeverity.ENFORCE,
        payload={"mode": "analysis_only"},
    )
    payload = override.model_dump()
    restored, err = validate("override_spec", payload)
    assert err is None
    assert restored.override_id == "override-1"
    assert restored.payload["mode"] == "analysis_only"


def test_event_round_trip() -> None:
    """Test Event schema round-trip serialization."""
    from agent_engine.schemas import Event, EventType

    event = Event(
        event_id="evt-1",
        task_id="task-1",
        stage_id="stage-1",
        type=EventType.AGENT,
        payload={"model": "gpt-4", "tokens": 150},
    )
    payload = event.model_dump()
    restored, err = validate("event", payload)
    assert err is None
    assert restored.type == EventType.AGENT
    assert restored.payload["tokens"] == 150


def test_task_mode_safe_modes() -> None:
    """Test TaskMode safe-mode values."""
    from agent_engine.schemas import TaskMode

    assert TaskMode.ANALYSIS_ONLY.value == "analysis_only"
    assert TaskMode.DRY_RUN.value == "dry_run"
    assert TaskMode.IMPLEMENT.value == "implement"
    assert TaskMode.REVIEW.value == "review"


# DEPRECATED: Pipeline schema is no longer part of canonical architecture
# The test_pipeline_round_trip test has been removed as Pipeline is not exported
