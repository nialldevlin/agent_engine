from agent_engine.config_loader import EngineConfig
from agent_engine.runtime.agent_runtime import AgentRuntime
from agent_engine.runtime.context import ContextAssembler
from agent_engine.runtime.dag_executor import DAGExecutor
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


def test_dag_executor_runs_through_stages() -> None:
    stages = {
        "s1": Node(stage_id="s1", name="agent", kind=NodeKind.AGENT, role=NodeRole.START, default_start=True, context="global"),
        "s2": Node(stage_id="s2", name="tool", kind=NodeKind.DETERMINISTIC, role=NodeRole.EXIT, context="global", tools=["test_tool"]),
    }
    workflow = WorkflowGraph(
        workflow_id="wf",
        nodes=list(stages.keys()),
        edges=[Edge(from_node_id="s1", to_node_id="s2")],
    )
    router = Router(workflow=workflow, stages=stages)
    task_manager = TaskManager()
    context_assembler = ContextAssembler()
    agent_runtime = AgentRuntime()
    tool_runtime = ToolRuntimeStub()
    executor = DAGExecutor(task_manager, router, context_assembler, agent_runtime, tool_runtime)

    spec = TaskSpec(task_spec_id="t1", request="do", mode=TaskMode.ANALYSIS_ONLY)
    task = task_manager.create_task(spec)

    final = executor.run(task)
    assert final.status == UniversalStatus.COMPLETED
    assert final.routing_trace
    assert "s2" in final.stage_results
    output = final.stage_results["s2"].output
    assert output["tool_stage"] == "s2"
    assert output["task"] == task.task_id


class ToolRuntimeStub:
    def run_tool_stage(self, task, node, context_package):
        return {"tool_stage": node.stage_id, "task": task.task_id}, None
