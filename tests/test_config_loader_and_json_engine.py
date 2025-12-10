from pathlib import Path

import pytest

from agent_engine.config_loader import EngineConfig, load_engine_config
from agent_engine.json_engine import repair_and_validate, validate
from agent_engine.schemas import (
    EngineError,
    EngineErrorCode,
    EngineErrorSource,
    NodeKind,
    NodeRole,
    TaskMode,
    TaskSpec,
    ToolCapability,
    ToolDefinition,
    ToolKind,
    ToolRiskLevel,
)
from agent_engine.security import check_tool_call


def _write_yaml(path: Path, payload) -> None:
    import yaml

    path.write_text(yaml.safe_dump(payload))


def test_config_loader_success(tmp_path: Path) -> None:
    agents = [{"agent_id": "a1", "role": "agent"}]
    tools = [
        {
            "tool_id": "t1",
            "kind": "deterministic",
            "name": "ls",
            "description": "List files",
            "inputs_schema_id": "task_spec",
            "outputs_schema_id": "event",
            "risk_level": "low",
        }
    ]
    # Nodes are now embedded in workflow.yaml (not separate manifest)
    workflow = {
        "workflow_id": "wf1",
        "nodes": [
            {"stage_id": "s1", "name": "start", "kind": "deterministic", "role": "start", "context": "global", "default_start": True},
            {"stage_id": "s2", "name": "end", "kind": "deterministic", "role": "exit", "context": "global"},
        ],
        "edges": [
            {"from_node_id": "s1", "to_node_id": "s2"}
        ],
    }

    _write_yaml(tmp_path / "agents.yaml", agents)
    _write_yaml(tmp_path / "tools.yaml", tools)
    _write_yaml(tmp_path / "workflow.yaml", workflow)

    config, err = load_engine_config(
        {
            "agents": tmp_path / "agents.yaml",
            "tools": tmp_path / "tools.yaml",
            "workflow": tmp_path / "workflow.yaml",
        }
    )

    assert err is None
    assert isinstance(config, EngineConfig)
    assert "a1" in config.agents
    assert "t1" in config.tools
    assert "s1" in config.nodes
    assert "s2" in config.nodes
    assert config.workflow is not None
    assert config.workflow.workflow_id == "wf1"


def test_config_loader_unknown_stage(tmp_path: Path) -> None:
    _write_yaml(tmp_path / "agents.yaml", [{"agent_id": "a1", "role": "agent"}])
    _write_yaml(tmp_path / "tools.yaml", [])
    # Workflow references a stage that is not defined
    _write_yaml(tmp_path / "workflow.yaml", {
        "workflow_id": "wf1",
        "nodes": ["missing"],
        "edges": [],
    })

    config, err = load_engine_config(
        {
            "agents": tmp_path / "agents.yaml",
            "tools": tmp_path / "tools.yaml",
            "workflow": tmp_path / "workflow.yaml",
        }
    )

    assert config is None
    assert isinstance(err, EngineError)
    assert err.code == EngineErrorCode.CONFIG
    assert err.source == EngineErrorSource.CONFIG_LOADER


def test_config_loader_cycle_detection(tmp_path: Path) -> None:
    _write_yaml(tmp_path / "agents.yaml", [{"agent_id": "a1", "role": "agent"}])
    _write_yaml(tmp_path / "tools.yaml", [])
    # Nodes embedded in workflow.yaml
    _write_yaml(
        tmp_path / "workflow.yaml",
        {
            "workflow_id": "wf1",
            "nodes": [
                {"stage_id": "s1", "name": "one", "kind": "deterministic", "role": "start", "context": "global", "default_start": True},
                {"stage_id": "s2", "name": "two", "kind": "agent", "role": "linear", "context": "global", "agent_id": "a1"},
            ],
            "edges": [
                {"from_node_id": "s1", "to_node_id": "s2"},
                {"from_node_id": "s2", "to_node_id": "s1"},
            ],
        },
    )

    config, err = load_engine_config(
        {
            "agents": tmp_path / "agents.yaml",
            "tools": tmp_path / "tools.yaml",
            "workflow": tmp_path / "workflow.yaml",
        }
    )

    assert config is None
    assert isinstance(err, EngineError)
    assert "Cycle" in err.message

def test_workflow_start_not_reaching_end(tmp_path: Path) -> None:
    _write_yaml(tmp_path / "agents.yaml", [{"agent_id": "a1", "role": "agent"}])
    _write_yaml(tmp_path / "tools.yaml", [])
    # Nodes embedded in workflow.yaml
    _write_yaml(
        tmp_path / "workflow.yaml",
        {
            "workflow_id": "wf1",
            "nodes": [
                {"stage_id": "s1", "name": "one", "kind": "deterministic", "role": "start", "context": "global", "default_start": True},
                {"stage_id": "s2", "name": "two", "kind": "deterministic", "role": "exit", "context": "global"},
            ],
            "edges": [],  # No path from s1 to s2
        },
    )

    config, err = load_engine_config(
        {
            "agents": tmp_path / "agents.yaml",
            "tools": tmp_path / "tools.yaml",
            "workflow": tmp_path / "workflow.yaml",
        }
    )

    assert config is None
    assert isinstance(err, EngineError)
    # Error should indicate unreachable stages or path issues
    assert ("cannot reach" in err.message or "Unreachable" in err.message)


def test_json_engine_validate_and_repair() -> None:
    payload = {"task_spec_id": "spec-1", "request": "hello", "mode": "analysis_only"}
    obj, err = validate("task_spec", payload)
    assert err is None
    assert isinstance(obj, TaskSpec)

    raw = '  { "task_spec_id": "spec-2", "request": "hi", "mode": "analysis_only" } trailing'
    obj2, err2 = repair_and_validate("task_spec", raw)
    assert err2 is None
    assert obj2.task_spec_id == "spec-2"

    bad = "not json at all"
    obj3, err3 = repair_and_validate("task_spec", bad)
    assert obj3 is None
    assert isinstance(err3, EngineError)
    assert err3.code == EngineErrorCode.JSON


def test_security_decisions() -> None:
    tool = ToolDefinition(
        tool_id="net",
        kind=ToolKind.DETERMINISTIC,
        name="net",
        description="net",
        inputs_schema_id="in",
        outputs_schema_id="out",
        capabilities=[ToolCapability.EXTERNAL_NETWORK],
        risk_level=ToolRiskLevel.HIGH,
    )
    decision = check_tool_call(tool, allow_network=False)
    assert decision.allowed is False

    allowed = check_tool_call(tool, allow_network=True)
    assert allowed.allowed is True
    assert allowed.require_review is True
