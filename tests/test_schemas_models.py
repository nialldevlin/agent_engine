import pytest
from pydantic import ValidationError

from agent_engine.json_engine import validate
from agent_engine.schemas import (
    AgentDefinition,
    AgentRole,
    Edge,
    EdgeType,
    EngineError,
    EngineErrorCode,
    EngineErrorSource,
    FailureCode,
    FailureSignature,
    Stage,
    StageType,
    Task,
    TaskMode,
    TaskSpec,
    TaskStatus,
    ToolDefinition,
    ToolKind,
    ToolRiskLevel,
    WorkflowGraph,
    get_schema_json,
)


def test_task_spec_and_task_instantiation() -> None:
    spec = TaskSpec(task_spec_id="spec-1", request="Fix bug", mode=TaskMode.ANALYSIS_ONLY)
    task = Task(task_id="task-1", spec=spec, pipeline_id="pipe-1")
    assert task.status == TaskStatus.PENDING
    assert task.spec.request == "Fix bug"


def test_task_invalid_missing_required() -> None:
    with pytest.raises(ValidationError):
        TaskSpec(request="missing id")  # type: ignore[arg-type]


def test_stage_and_workflow_graph() -> None:
    stage = Stage(stage_id="s1", name="do", type=StageType.AGENT)
    graph = WorkflowGraph(workflow_id="wf1", stages=[stage.stage_id], edges=[])
    assert graph.workflow_id == "wf1"
    assert graph.stages == ["s1"]


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
    stage = Stage(stage_id="s-linear", name="Linear", type=StageType.LINEAR, terminal=False)
    payload = stage.model_dump()
    restored, err = validate("stage", payload)
    assert err is None
    assert restored.stage_id == stage.stage_id


def test_workflow_round_trip_validation() -> None:
    graph = WorkflowGraph(
        workflow_id="wf2",
        stages=["start", "end"],
        edges=[Edge(from_stage_id="start", to_stage_id="end", edge_type=EdgeType.NORMAL)],
    )
    payload = graph.model_dump()
    restored, err = validate("workflow_graph", payload)
    assert err is None
    assert restored.workflow_id == "wf2"
