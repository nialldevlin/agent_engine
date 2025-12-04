import pytest

from agent_engine.runtime.agent_runtime import AgentRuntime
from agent_engine.runtime.tool_runtime import ToolRuntime
from agent_engine.schemas import (
    EngineErrorCode,
    EngineErrorSource,
    Stage,
    StageType,
    TaskMode,
    TaskSpec,
    Task,
    TaskStatus,
    ToolCapability,
    ToolDefinition,
    ToolKind,
    ToolRiskLevel,
)
from agent_engine.runtime.context import ContextAssembler
from agent_engine.schemas import ContextItem, ContextRequest


class FakeLLM:
    def __init__(self, payload):
        self.payload = payload

    def generate(self, prompt):
        return self.payload


def test_agent_runtime_validates_output_schema() -> None:
    llm = FakeLLM({"task_spec_id": "s1", "request": "x", "mode": "analysis_only"})
    runtime = AgentRuntime(llm_client=llm)
    stage = Stage(stage_id="s1", name="agent", type=StageType.AGENT, outputs_schema_id="task_spec")
    spec = TaskSpec(task_spec_id="s1", request="hello", mode=TaskMode.ANALYSIS_ONLY)
    task = Task(task_id="task-agent-1", spec=spec, pipeline_id="pipe", status=TaskStatus.PENDING, metadata={})
    context = ContextAssembler().build_context(task, ContextRequest(context_request_id="c1", budget_tokens=0, domains=[], history_types=[]))
    output, err = runtime.run_agent_stage(task, stage, context)
    assert err is None
    assert output.task_spec_id == "s1"


def test_agent_runtime_schema_error() -> None:
    llm = FakeLLM({"not": "matching"})
    runtime = AgentRuntime(llm_client=llm)
    stage = Stage(stage_id="s1", name="agent", type=StageType.AGENT, outputs_schema_id="task_spec")
    spec = TaskSpec(task_spec_id="s1", request="hello", mode=TaskMode.ANALYSIS_ONLY)
    task = Task(task_id="task-agent-2", spec=spec, pipeline_id="pipe", status=TaskStatus.PENDING, metadata={})
    context = ContextAssembler().build_context(task, ContextRequest(context_request_id="c1", budget_tokens=0, domains=[], history_types=[]))
    output, err = runtime.run_agent_stage(task, stage, context)
    assert output is None
    assert err is not None
    assert err.code == EngineErrorCode.VALIDATION


def test_tool_runtime_security_gate() -> None:
    tools = {
        "net": ToolDefinition(
            tool_id="net",
            kind=ToolKind.DETERMINISTIC,
            name="net",
            description="",
            inputs_schema_id="in",
            outputs_schema_id="out",
            capabilities=[ToolCapability.EXTERNAL_NETWORK],
            risk_level=ToolRiskLevel.HIGH,
        )
    }
    runtime = ToolRuntime(tools=tools, tool_handlers={})
    stage = Stage(stage_id="t1", name="tool", type=StageType.TOOL, tool_id="net")
    spec = TaskSpec(task_spec_id="task", request="r", mode=TaskMode.ANALYSIS_ONLY)
    task = Task(task_id="task-tool-1", spec=spec, pipeline_id="pipe", status=TaskStatus.PENDING, metadata={})
    context = ContextAssembler().build_context(task, ContextRequest(context_request_id="c1", budget_tokens=0, domains=[], history_types=[]))
    output, err = runtime.run_tool_stage(task, stage, context)
    assert output is None
    assert err is not None
    assert err.code == EngineErrorCode.SECURITY
    assert err.source == EngineErrorSource.TOOL_RUNTIME
