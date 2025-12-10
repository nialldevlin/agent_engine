"""Schema registry and JSON Schema export."""

from __future__ import annotations

from typing import Dict, Type

from .agent import AgentDefinition, AgentManifest
from .errors import EngineError, FailureSignature
from .event import Event
from .memory import (
    ContextFingerprint,
    ContextItem,
    ContextPackage,
    ContextProfile,
    ContextProfileSource,
    ContextRequest,
    MemoryConfig,
)
from .override import OverrideSpec
from .stage import Node, NodeKind, NodeRole
from .task import Task, TaskLifecycle, TaskSpec, UniversalStatus
from .tool import ToolCallRecord, ToolDefinition, ToolPlan, ToolStep
from .tool_io import ExecutionInput, ExecutionOutput, GatherContextInput, GatherContextOutput
from .workflow import Edge, WorkflowGraph

SchemaType = Type


SCHEMA_REGISTRY: Dict[str, SchemaType] = {
    "task_spec": TaskSpec,
    "task": Task,
    "failure_signature": FailureSignature,
    "node": Node,
    "edge": Edge,
    "workflow_graph": WorkflowGraph,
    "agent_definition": AgentDefinition,
    "agent_manifest": AgentManifest,
    "tool_definition": ToolDefinition,
    "tool_plan": ToolPlan,
    "tool_step": ToolStep,
    "tool_call_record": ToolCallRecord,
    "gather_context_input": GatherContextInput,
    "gather_context_output": GatherContextOutput,
    "execution_input": ExecutionInput,
    "execution_output": ExecutionOutput,
    "memory_config": MemoryConfig,
    "context_item": ContextItem,
    "context_fingerprint": ContextFingerprint,
    "context_profile": ContextProfile,
    "context_profile_source": ContextProfileSource,
    "context_request": ContextRequest,
    "context_package": ContextPackage,
    "event": Event,
    "override_spec": OverrideSpec,
    "engine_error": EngineError,
}


def get_schema_json(name: str) -> Dict:
    """Return JSON Schema for a registered schema name."""
    if name not in SCHEMA_REGISTRY:
        raise KeyError(f"Schema '{name}' is not registered")
    model = SCHEMA_REGISTRY[name]
    return model.model_json_schema()
