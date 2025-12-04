"""Runtime exports and helpers."""

from agent_engine.runtime.agent_runtime import AgentRuntime
from agent_engine.runtime.context import ContextAssembler, ContextStore
from agent_engine.runtime.llm_client import AnthropicLLMClient, LLMClient, MockLLMClient, OllamaLLMClient
from agent_engine.runtime.pipeline_executor import PipelineExecutor
from agent_engine.runtime.router import Router
from agent_engine.runtime.task_manager import TaskManager
from agent_engine.runtime.tool_runtime import ToolRuntime

__all__ = [
    "AgentRuntime",
    "ContextAssembler",
    "ContextStore",
    "AnthropicLLMClient",
    "OllamaLLMClient",
    "MockLLMClient",
    "LLMClient",
    "PipelineExecutor",
    "Router",
    "TaskManager",
    "ToolRuntime",
]


def run_task(task_spec, engine_config, agent_runtime=None, tool_runtime=None):
    """Convenience entry point to run a task through the pipeline."""
    task_manager = TaskManager()
    router = Router(workflow=engine_config.workflow, pipelines=engine_config.pipelines, stages=engine_config.stages)
    context = ContextAssembler()
    agent_rt = agent_runtime or AgentRuntime(llm_client=None)
    tool_rt = tool_runtime or ToolRuntime(engine_config.tools)
    pipeline = router.choose_pipeline(task_spec)
    task = task_manager.create_task(task_spec, pipeline_id=pipeline.pipeline_id)
    executor = PipelineExecutor(task_manager, router, context, agent_rt, tool_rt)
    return executor.run(task, pipeline_id=pipeline.pipeline_id)
