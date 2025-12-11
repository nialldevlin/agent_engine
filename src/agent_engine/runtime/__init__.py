"""Runtime exports and helpers."""

from agent_engine.runtime.agent_runtime import AgentRuntime
from agent_engine.runtime.context import ContextAssembler
from agent_engine.runtime.llm_client import AnthropicLLMClient, LLMClient, MockLLMClient, OllamaLLMClient
from agent_engine.runtime.dag_executor import DAGExecutor
from agent_engine.runtime.router import Router
from agent_engine.runtime.task_manager import TaskManager
from agent_engine.runtime.tool_runtime import ToolRuntime
from agent_engine.runtime.node_executor import NodeExecutor
from agent_engine.runtime.deterministic_registry import DeterministicRegistry
from agent_engine.runtime.artifact_store import ArtifactStore
from agent_engine.runtime.metadata_collector import collect_engine_metadata
from agent_engine.runtime.evaluator import Evaluator
from agent_engine.runtime.metrics_collector import MetricsCollector
from agent_engine.runtime.policy_evaluator import PolicyEvaluator

__all__ = [
    "AgentRuntime",
    "ContextAssembler",
    "AnthropicLLMClient",
    "OllamaLLMClient",
    "MockLLMClient",
    "LLMClient",
    "DAGExecutor",
    "Router",
    "TaskManager",
    "ToolRuntime",
    "NodeExecutor",
    "DeterministicRegistry",
    "ArtifactStore",
    "collect_engine_metadata",
    "Evaluator",
    "MetricsCollector",
    "PolicyEvaluator",
]


def run_task(task_spec, engine_config, agent_runtime=None, tool_runtime=None):
    """Convenience entry point to run a task through the DAG workflow."""
    task_manager = TaskManager()
    router = Router(workflow=engine_config.workflow, stages=engine_config.stages)
    context = ContextAssembler()
    agent_rt = agent_runtime or AgentRuntime(llm_client=None)
    tool_rt = tool_runtime or ToolRuntime(engine_config.tools)
    task = task_manager.create_task(task_spec)
    executor = DAGExecutor(task_manager, router, context, agent_rt, tool_rt)
    return executor.run(task)
