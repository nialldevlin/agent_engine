"""Configuration loader for Agent Engine manifests."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml
from pydantic import ValidationError

from agent_engine import __version__
from agent_engine.json_engine import validate
from agent_engine.schemas import (
    AgentDefinition,
    EngineError,
    EngineErrorCode,
    EngineErrorSource,
    MemoryConfig,
    Pipeline,
    Severity,
    Stage,
    SCHEMA_REGISTRY,
    ToolDefinition,
    WorkflowGraph,
)

@dataclass(frozen=True)
class EngineConfig:
    agents: Dict[str, AgentDefinition] = field(default_factory=dict)
    tools: Dict[str, ToolDefinition] = field(default_factory=dict)
    stages: Dict[str, Stage] = field(default_factory=dict)
    workflow: Optional[WorkflowGraph] = None
    pipelines: Dict[str, Pipeline] = field(default_factory=dict)
    memory: Optional[MemoryConfig] = None
    version: str = __version__


def load_engine_config(manifests: Dict[str, Path]) -> Tuple[Optional[EngineConfig], Optional[EngineError]]:
    """Load all manifests (agents, tools, stages, workflow, pipelines, memory).

    Expects manifests mapping keys: agents, tools, stages, workflow, pipelines, memory (optional).
    Returns (EngineConfig, error). On first validation failure, returns (None, EngineError).
    """
    try:
        agents = _load_list(manifests.get("agents"), AgentDefinition, "agent_definition")
        tools = _load_list(manifests.get("tools"), ToolDefinition, "tool_definition")
        stages = _load_list(manifests.get("stages"), Stage, "stage")
        schema_error = _validate_tool_schemas(tools)
        if schema_error:
            return None, schema_error
        schema_error = _validate_tool_schemas(_load_list(manifests.get("tools"), ToolDefinition, "tool_definition"))
        if schema_error:
            return None, schema_error
        tools = _load_list(manifests.get("tools"), ToolDefinition, "tool_definition")

        workflow_payload = _load_file(manifests.get("workflow"))
        workflow, err = validate("workflow_graph", workflow_payload) if workflow_payload is not None else (None, None)
        if err:
            return None, err

        pipelines_payload = _load_file(manifests.get("pipelines"))
        pipelines_list = pipelines_payload or []
        pipelines: Dict[str, Pipeline] = {}
        for item in pipelines_list:
            obj, err = validate("pipeline", item)
            if err:
                return None, err
            pipelines[obj.pipeline_id] = obj  # type: ignore[arg-type]

        memory_payload = _load_file(manifests.get("memory"))
        memory: Optional[MemoryConfig] = None
        if memory_payload:
            memory, err = validate("memory_config", memory_payload)
            if err:
                return None, err

        # Link workflow stages consistency check
        if workflow:
            unknown = set(workflow.stages) - set(stages.keys())
            if unknown:
                return None, _error(f"Workflow references unknown stages: {unknown}")
            graph_error = _validate_workflow(workflow, pipelines)
            if graph_error:
                return None, graph_error

        return (
            EngineConfig(
                agents=agents,
                tools=tools,
                stages=stages,
                workflow=workflow,
                pipelines=pipelines,
                memory=memory,
            ),
            None,
        )
    except ValidationError as exc:
        return None, _error("Validation error", exc.errors())
    except Exception as exc:  # pragma: no cover
        return None, _error(f"Unexpected error: {exc}")


def _load_file(path: Optional[Path]):
    if path is None:
        return None
    if not path.exists():
        raise FileNotFoundError(path)
    text = path.read_text()
    if path.suffix.lower() in {".yaml", ".yml"}:
        return yaml.safe_load(text)
    return json.loads(text)


def _load_list(path: Optional[Path], model, schema_name: str):
    payload = _load_file(path)
    items = payload or []
    result = {}
    for item in items:
        obj, err = validate(schema_name, item)
        if err:
            raise ValidationError(err.details, model=model)
        key = getattr(obj, f"{schema_name.split('_')[0]}_id", None) or getattr(obj, "stage_id", None)
        if key is None:
            raise ValidationError([{"msg": "Missing id"}], model=model)
        result[key] = obj
    return result


def _error(message: str, details=None) -> EngineError:
    return EngineError(
        error_id="config_error",
        code=EngineErrorCode.VALIDATION,
        message=message,
        source=EngineErrorSource.CONFIG_LOADER,
        severity=Severity.ERROR,
        details=details,
    )


def _validate_tool_schemas(tools: Dict[str, ToolDefinition]) -> Optional[EngineError]:
    missing: list[str] = []
    for tool in tools.values():
        for kind, schema_id in (("inputs", tool.inputs_schema_id), ("outputs", tool.outputs_schema_id)):
            if schema_id and schema_id not in SCHEMA_REGISTRY:
                missing.append(f"{tool.tool_id} {kind}='{schema_id}'")
    if missing:
        joined = ", ".join(missing)
        return _error(f"Unknown tool schema references: {joined}")
    return None


def _validate_workflow(workflow: WorkflowGraph, pipelines: Dict[str, Pipeline]) -> Optional[EngineError]:
    adjacency = {stage_id: [] for stage_id in workflow.stages}
    for edge in workflow.edges:
        adjacency.setdefault(edge.from_stage_id, []).append(edge.to_stage_id)

    if _has_cycle(adjacency):
        return _error("Workflow graph contains cycles")

    for pipeline in pipelines.values():
        missing_starts = set(pipeline.start_stage_ids) - set(workflow.stages)
        missing_ends = set(pipeline.end_stage_ids) - set(workflow.stages)
        if missing_starts or missing_ends:
            return _error(f"Pipeline {pipeline.pipeline_id} references unknown stages")

        for start in pipeline.start_stage_ids:
            if not _reaches_end(start, set(pipeline.end_stage_ids), adjacency):
                return _error(f"Pipeline {pipeline.pipeline_id} start {start} cannot reach an end node")
    return None


def _has_cycle(graph: Dict[str, list]) -> bool:
    visited: Dict[str, str] = {}

    def dfs(node: str) -> bool:
        visited[node] = "visiting"
        for neighbor in graph.get(node, []):
            if visited.get(neighbor) == "visiting":
                return True
            if visited.get(neighbor) != "visited" and dfs(neighbor):
                return True
        visited[node] = "visited"
        return False

    for node in graph:
        if visited.get(node) is None:
            if dfs(node):
                return True
    return False


def _reaches_end(start: str, end_nodes: set[str], adjacency: Dict[str, list]) -> bool:
    stack = [start]
    seen = set()
    while stack:
        node = stack.pop()
        if node in end_nodes:
            return True
        if node in seen:
            continue
        seen.add(node)
        stack.extend(adjacency.get(node, []))
    return False
