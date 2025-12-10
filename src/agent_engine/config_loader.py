"""Configuration loader for Agent Engine manifests."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

from agent_engine import __version__
from agent_engine.json_engine import validate
from agent_engine.schemas import (
    AgentDefinition,
    EngineError,
    EngineErrorCode,
    EngineErrorSource,
    MemoryConfig,
    Node,
    Severity,
    SCHEMA_REGISTRY,
    ToolDefinition,
    WorkflowGraph,
)
from agent_engine.schemas.workflow import validate_workflow_graph


@dataclass(frozen=True)
class EngineConfig:
    agents: Dict[str, AgentDefinition] = field(default_factory=dict)
    tools: Dict[str, ToolDefinition] = field(default_factory=dict)
    nodes: Dict[str, Node] = field(default_factory=dict)
    workflow: Optional[WorkflowGraph] = None
    memory: Optional[MemoryConfig] = None
    version: str = __version__


def load_engine_config(manifests: Dict[str, Path]) -> Tuple[Optional[EngineConfig], Optional[EngineError]]:
    """Load all manifests (agents, tools, workflow, memory).

    Note: stages are now embedded in workflow.yaml, not loaded separately.
    """
    try:
        agents, err = _load_list(manifests.get("agents"), "agent_definition")
        if err:
            return None, err
        tools, err = _load_list(manifests.get("tools"), "tool_definition")
        if err:
            return None, err

        schema_error = _validate_tool_schemas(tools)
        if schema_error:
            return None, schema_error

        workflow_payload, err = _load_file(manifests.get("workflow"))
        if err:
            return None, err
        workflow: Optional[WorkflowGraph] = None
        nodes: Dict[str, Node] = {}
        if workflow_payload is not None:
            # Extract nodes from embedded objects BEFORE validation if they exist
            if isinstance(workflow_payload, dict) and 'nodes' in workflow_payload:
                nodes_in_payload = workflow_payload.get('nodes', [])
                if nodes_in_payload and isinstance(nodes_in_payload[0], dict):
                    # Convert embedded node dicts to Node objects
                    for node_dict in nodes_in_payload:
                        node_obj, validation_err = validate("node", node_dict)
                        if validation_err:
                            return None, _from_validation_error("node", validation_err)
                        nodes[node_obj.stage_id] = node_obj
                    # Replace node dicts with stage IDs in payload for validation
                    workflow_payload['nodes'] = [n.stage_id for n in nodes.values()]

            workflow_obj, validation_err = validate("workflow_graph", workflow_payload)
            if validation_err:
                return None, _from_validation_error("workflow", validation_err)
            workflow = workflow_obj

        memory_payload, err = _load_file(manifests.get("memory"), required=False)
        if err:
            return None, err
        memory: Optional[MemoryConfig] = None
        if memory_payload:
            memory, validation_err = validate("memory_config", memory_payload)
            if validation_err:
                return None, _from_validation_error("memory", validation_err)

        if workflow:
            graph_error = _validate_workflow(workflow, nodes)
            if graph_error:
                return None, graph_error

        return (
            EngineConfig(
                agents=agents,
                tools=tools,
                nodes=nodes,
                workflow=workflow,
                memory=memory,
            ),
            None,
        )

    except Exception as exc:  # pragma: no cover
        return None, _error(f"Unexpected error: {exc}")


def _load_file(path: Optional[Path], *, required: bool = True):
    if path is None:
        if required:
            return None, _error("Required manifest path not provided")
        return None, None

    if not path.exists():
        if required:
            return None, _error(f"Manifest not found: {path}")
        return None, None

    text = path.read_text()
    try:
        if path.suffix.lower() in {".yaml", ".yml"}:
            return yaml.safe_load(text), None
        return json.loads(text), None
    except (yaml.YAMLError, json.JSONDecodeError) as exc:
        return None, _error(f"Failed to parse manifest {path.name}", {"error": str(exc)})


def _load_list(path: Optional[Path], schema_name: str, *, required: bool = True):
    payload, err = _load_file(path, required=required)
    if err:
        return {}, err
    items = payload or []
    result = {}
    for item in items:
        obj, validation_err = validate(schema_name, item)
        if validation_err:
            return {}, _from_validation_error(schema_name, validation_err)
        key = _resolve_id(obj)
        if key is None:
            return {}, _error(f"{schema_name} manifest entry missing id field")
        result[key] = obj
    return result, None


def _resolve_id(obj) -> Optional[str]:
    for attr in ("agent_id", "tool_id", "stage_id"):
        value = getattr(obj, attr, None)
        if value is not None:
            return value
    return None


def _error(message: str, details=None) -> EngineError:
    return EngineError(
        error_id="config_error",
        code=EngineErrorCode.CONFIG,
        message=message,
        source=EngineErrorSource.CONFIG_LOADER,
        severity=Severity.ERROR,
        details=details,
    )


def _from_validation_error(schema_name: str, validation_error: EngineError) -> EngineError:
    details = validation_error.details or {}
    merged_details = {"schema": schema_name, **details} if isinstance(details, dict) else {"schema": schema_name}
    return _error(f"{schema_name} manifest validation failed", merged_details)


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


def _validate_workflow(workflow: WorkflowGraph, nodes: Dict[str, Node]) -> Optional[EngineError]:
    try:
        validate_workflow_graph(workflow, nodes=nodes)
    except ValueError as exc:
        return _error(str(exc))
    return None


