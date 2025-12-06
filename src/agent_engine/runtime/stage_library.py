"""Minimal stage library helpers used by the executor or other orchestrators.

Each function delegates to the provided runtime dependencies (which may be
objects or a dict containing runtimes) and implements robust error handling.

These helpers are intentionally small and deterministic so tests can exercise
stage-level behavior without requiring full production wiring.
"""
from typing import Any, Dict, Tuple

from agent_engine.schemas import EngineError, Stage, Task


def _get_runtime(runtime_dependencies, name: str):
    """Helper to extract a runtime by name from either a dict or an object."""
    if runtime_dependencies is None:
        return None
    if isinstance(runtime_dependencies, dict):
        return runtime_dependencies.get(name)
    return getattr(runtime_dependencies, name, None)


def run_agent_stage(task: Task, stage: Stage, context, runtime_dependencies) -> Tuple[Any | None, EngineError | None]:
    """Run an agent stage using the provided AgentRuntime.

    runtime_dependencies may be either a dict containing 'agent_runtime' or
    an object with attribute `agent_runtime`. Returns (output, EngineError|None).
    """
    agent_runtime = _get_runtime(runtime_dependencies, "agent_runtime") or _get_runtime(runtime_dependencies, "agent")
    if agent_runtime is None:
        return None, EngineError(error_id="no_agent_runtime", code=None, message="AgentRuntime not provided", source=None, severity=None)

    try:
        return agent_runtime.run_agent_stage(task, stage, context)
    except Exception as exc:  # Defensive: convert unexpected exceptions to EngineError
        return None, EngineError(error_id="agent_stage_exception", code=None, message=str(exc), source=None, severity=None)


def run_tool_stage(task: Task, stage: Stage, context, runtime_dependencies) -> Tuple[Any | None, EngineError | None]:
    """Run a tool stage using the provided ToolRuntime.

    Returns (output, EngineError|None).
    """
    tool_runtime = _get_runtime(runtime_dependencies, "tool_runtime") or _get_runtime(runtime_dependencies, "tool")
    if tool_runtime is None:
        return None, EngineError(error_id="no_tool_runtime", code=None, message="ToolRuntime not provided", source=None, severity=None)

    try:
        return tool_runtime.run_tool_stage(task, stage, context)
    except Exception as exc:
        return None, EngineError(error_id="tool_stage_exception", code=None, message=str(exc), source=None, severity=None)


def run_decision_stage(task: Task, stage: Stage, context, runtime_dependencies) -> Tuple[Any | None, EngineError | None]:
    """Run a decision stage.

    Default behaviour is to delegate to the AgentRuntime (so decisions can be
    evaluated by an LLM). If the agent returns a non-dict, we return it as-is
    and the caller (PipelineExecutor) will convert it to a decision structure.
    """
    agent_runtime = _get_runtime(runtime_dependencies, "agent_runtime") or _get_runtime(runtime_dependencies, "agent")
    if agent_runtime is None:
        return None, EngineError(error_id="no_agent_runtime_for_decision", code=None, message="AgentRuntime not provided for decision stage", source=None, severity=None)

    try:
        return agent_runtime.run_agent_stage(task, stage, context)
    except Exception as exc:
        return None, EngineError(error_id="decision_stage_exception", code=None, message=str(exc), source=None, severity=None)


def run_merge_stage(task: Task, stage: Stage, context, runtime_dependencies) -> Tuple[Any | None, EngineError | None]:
    """Aggregate prior stage outputs for the given task.

    The merge implementation inspects the Task stored in TaskManager (if
    provided) and returns a dict mapping stage_id -> output for all recorded
    stage results. This is intentionally simple and deterministic.
    """
    task_manager = _get_runtime(runtime_dependencies, "task_manager") or _get_runtime(runtime_dependencies, "manager")
    try:
        if task_manager is None:
            # Best-effort: if the task object itself has stage_results, use it
            if hasattr(task, "stage_results"):
                return {sid: rec.output for sid, rec in task.stage_results.items()}, None
            return None, None

        stored = task_manager.tasks.get(task.task_id)
        if stored is None:
            return None, None

        return {sid: rec.output for sid, rec in stored.stage_results.items()}, None
    except Exception as exc:
        return None, EngineError(error_id="merge_stage_exception", code=None, message=str(exc), source=None, severity=None)
