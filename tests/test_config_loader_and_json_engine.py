from pathlib import Path

import pytest

from agent_engine.config_loader import EngineConfig, load_engine_config
from agent_engine.json_engine import repair_and_validate, validate
from agent_engine.schemas import (
    EngineErrorCode,
    EngineErrorSource,
    EngineError,
    StageType,
    TaskSpec,
    TaskMode,
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
    agents = [{"agent_id": "a1", "role": "knight"}]
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
    stages = [{"stage_id": "s1", "name": "start", "type": "agent", "entrypoint": True, "terminal": True}]
    workflow = {"workflow_id": "wf1", "stages": ["s1"], "edges": []}
    pipelines = [
        {
            "pipeline_id": "p1",
            "name": "main",
            "description": "test pipeline",
            "workflow_id": "wf1",
            "start_stage_ids": ["s1"],
            "end_stage_ids": ["s1"],
            "allowed_modes": [],
            "fallback_end_stage_ids": [],
        }
    ]

    _write_yaml(tmp_path / "agents.yaml", agents)
    _write_yaml(tmp_path / "tools.yaml", tools)
    _write_yaml(tmp_path / "stages.yaml", stages)
    _write_yaml(tmp_path / "workflow.yaml", workflow)
    _write_yaml(tmp_path / "pipelines.yaml", pipelines)

    config, err = load_engine_config(
        {
            "agents": tmp_path / "agents.yaml",
            "tools": tmp_path / "tools.yaml",
            "stages": tmp_path / "stages.yaml",
            "workflow": tmp_path / "workflow.yaml",
            "pipelines": tmp_path / "pipelines.yaml",
        }
    )

    assert err is None
    assert isinstance(config, EngineConfig)
    assert "a1" in config.agents
    assert "t1" in config.tools
    assert "s1" in config.stages
    assert "p1" in config.pipelines
    assert config.workflow is not None
    assert config.workflow.workflow_id == "wf1"


def test_config_loader_unknown_stage(tmp_path: Path) -> None:
    _write_yaml(tmp_path / "agents.yaml", [{"agent_id": "a1", "role": "knight"}])
    _write_yaml(tmp_path / "tools.yaml", [])
    _write_yaml(tmp_path / "stages.yaml", [])
    _write_yaml(tmp_path / "workflow.yaml", {"workflow_id": "wf1", "stages": ["missing"], "edges": []})
    _write_yaml(
        tmp_path / "pipelines.yaml",
        [
            {
                "pipeline_id": "p1",
                "name": "main",
                "description": "test pipeline",
                "workflow_id": "wf1",
                "start_stage_ids": ["missing"],
                "end_stage_ids": ["missing"],
                "allowed_modes": [],
                "fallback_end_stage_ids": [],
            }
        ],
    )

    config, err = load_engine_config(
        {
            "agents": tmp_path / "agents.yaml",
            "tools": tmp_path / "tools.yaml",
            "stages": tmp_path / "stages.yaml",
            "workflow": tmp_path / "workflow.yaml",
            "pipelines": tmp_path / "pipelines.yaml",
        }
    )

    assert config is None
    assert isinstance(err, EngineError)
    assert err.code == EngineErrorCode.VALIDATION
    assert err.source == EngineErrorSource.CONFIG_LOADER


def test_config_loader_cycle_detection(tmp_path: Path) -> None:
    _write_yaml(tmp_path / "agents.yaml", [{"agent_id": "a1", "role": "knight"}])
    _write_yaml(tmp_path / "tools.yaml", [])
    _write_yaml(
        tmp_path / "stages.yaml",
        [
            {"stage_id": "s1", "name": "one", "type": "agent"},
            {"stage_id": "s2", "name": "two", "type": "agent"},
        ],
    )
    _write_yaml(
        tmp_path / "workflow.yaml",
        {
            "workflow_id": "wf1",
            "stages": ["s1", "s2"],
            "edges": [
                {"from_stage_id": "s1", "to_stage_id": "s2"},
                {"from_stage_id": "s2", "to_stage_id": "s1"},
            ],
        },
    )
    _write_yaml(
        tmp_path / "pipelines.yaml",
        [
            {
                "pipeline_id": "p1",
                "name": "main",
                "description": "cyclic",
                "workflow_id": "wf1",
                "start_stage_ids": ["s1"],
                "end_stage_ids": ["s2"],
                "allowed_modes": [],
                "fallback_end_stage_ids": [],
            }
        ],
    )

    config, err = load_engine_config(
        {
            "agents": tmp_path / "agents.yaml",
            "tools": tmp_path / "tools.yaml",
            "stages": tmp_path / "stages.yaml",
            "workflow": tmp_path / "workflow.yaml",
            "pipelines": tmp_path / "pipelines.yaml",
        }
    )

    assert config is None
    assert isinstance(err, EngineError)
    assert "contains cycles" in err.message


def test_pipeline_start_not_reaching_end(tmp_path: Path) -> None:
    _write_yaml(tmp_path / "agents.yaml", [{"agent_id": "a1", "role": "knight"}])
    _write_yaml(tmp_path / "tools.yaml", [])
    _write_yaml(
        tmp_path / "stages.yaml",
        [
            {"stage_id": "s1", "name": "one", "type": "agent"},
            {"stage_id": "s2", "name": "two", "type": "agent"},
        ],
    )
    _write_yaml(
        tmp_path / "workflow.yaml",
        {"workflow_id": "wf1", "stages": ["s1", "s2"], "edges": []},
    )
    _write_yaml(
        tmp_path / "pipelines.yaml",
        [
            {
                "pipeline_id": "p1",
                "name": "main",
                "description": "disconnected",
                "workflow_id": "wf1",
                "start_stage_ids": ["s1"],
                "end_stage_ids": ["s2"],
                "allowed_modes": [],
                "fallback_end_stage_ids": [],
            }
        ],
    )

    config, err = load_engine_config(
        {
            "agents": tmp_path / "agents.yaml",
            "tools": tmp_path / "tools.yaml",
            "stages": tmp_path / "stages.yaml",
            "workflow": tmp_path / "workflow.yaml",
            "pipelines": tmp_path / "pipelines.yaml",
        }
    )

    assert config is None
    assert isinstance(err, EngineError)
    assert "cannot reach an end node" in err.message


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
