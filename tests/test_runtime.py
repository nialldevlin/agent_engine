from agent_engine.config_loader import EngineConfig
from agent_engine.runtime.agent_runtime import AgentRuntime
from agent_engine.runtime.context import ContextAssembler
from agent_engine.runtime.pipeline_executor import PipelineExecutor
from agent_engine.runtime.router import Router
from agent_engine.runtime.task_manager import TaskManager
from agent_engine.schemas import (
    Edge,
    Pipeline,
    Stage,
    StageType,
    TaskMode,
    TaskSpec,
    TaskStatus,
    WorkflowGraph,
)


def test_pipeline_executor_runs_through_stages() -> None:
    stages = {
        "s1": Stage(stage_id="s1", name="agent", type=StageType.AGENT, entrypoint=True),
        "s2": Stage(stage_id="s2", name="tool", type=StageType.TOOL, terminal=True),
    }
    workflow = WorkflowGraph(workflow_id="wf", stages=list(stages.keys()), edges=[Edge(from_stage_id="s1", to_stage_id="s2")])
    pipeline = Pipeline(
        pipeline_id="p1",
        name="pipeline",
        description="",
        workflow_id="wf",
        start_stage_ids=["s1"],
        end_stage_ids=["s2"],
        allowed_modes=[],
        fallback_end_stage_ids=[],
    )
    router = Router(workflow=workflow, pipelines={"p1": pipeline}, stages=stages)
    task_manager = TaskManager()
    context_assembler = ContextAssembler()
    agent_runtime = AgentRuntime()
    tool_runtime = ToolRuntimeStub()
    executor = PipelineExecutor(task_manager, router, context_assembler, agent_runtime, tool_runtime)

    spec = TaskSpec(task_spec_id="t1", request="do", mode=TaskMode.ANALYSIS_ONLY)
    task = task_manager.create_task(spec, pipeline_id=pipeline.pipeline_id)

    final = executor.run(task, pipeline_id=pipeline.pipeline_id)
    assert final.status == TaskStatus.COMPLETED
    assert final.routing_trace
    assert "s2" in final.stage_results
    output = final.stage_results["s2"].output
    assert output["tool_stage"] == "s2"
    assert output["task"] == task.task_id


class ToolRuntimeStub:
    def run_tool_stage(self, task, stage, context_package):
        return {"tool_stage": stage.stage_id, "task": task.task_id}, None


def test_engine_from_config_dir_runs_basic_llm_agent():
    from tests.helpers.basic_llm_agent import build_engine

    engine = build_engine()
    task = engine.run_one("list files", mode="implement")
    assert task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED)
    assert task.stage_results
    assert task.pipeline_id
