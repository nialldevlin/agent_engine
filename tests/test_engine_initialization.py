"""
Comprehensive test coverage for Agent Engine initialization.

Tests the Engine.from_config_dir() and Engine.run() methods with focus on:
- Successful minimal config loading
- Manifest validation and error handling
- DAG construction and validation
- Memory store and adapter initialization
- Schema loading
- Context profile validation
"""

import pytest
import tempfile
import os
import json
from pathlib import Path

from agent_engine import (
    Engine,
    ManifestLoadError,
    SchemaValidationError,
    DAGValidationError,
)
from agent_engine.memory_stores import MemoryStore
from agent_engine.adapters import AdapterRegistry


def _write_yaml(path: Path, data) -> None:
    """Helper to write YAML files."""
    import yaml
    path.write_text(yaml.safe_dump(data))


def _write_json(path: Path, data) -> None:
    """Helper to write JSON files."""
    path.write_text(json.dumps(data))


class TestEngineInitializationMinimal:
    """Test successful Engine initialization with minimal config."""

    def _create_minimal_config(self, tmp_path):
        """Create a minimal valid config directory."""
        _write_yaml(tmp_path / "workflow.yaml", {
            "nodes": [
                {"stage_id": "start", "name": "start", "kind": "deterministic", "role": "start",
                 "context": "none", "default_start": True},
                {"stage_id": "main", "name": "main", "kind": "agent", "role": "linear",
                 "context": "global", "agent_id": "a1"},
                {"stage_id": "exit", "name": "exit", "kind": "deterministic", "role": "exit",
                 "context": "none"}
            ],
            "edges": [
                {"from_node_id": "start", "to_node_id": "main"},
                {"from_node_id": "main", "to_node_id": "exit"}
            ]
        })
        _write_yaml(tmp_path / "agents.yaml", {
            "agents": [{"id": "a1", "kind": "agent",
                       "llm": "anthropic/claude-3-5-sonnet"}]
        })
        _write_yaml(tmp_path / "tools.yaml", {"tools": []})

    def test_engine_from_config_dir_minimal(self):
        """Test loading minimal config successfully."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            self._create_minimal_config(tmp_path)

            engine = Engine.from_config_dir(tmp_dir)

            assert engine is not None
            assert engine.workflow is not None
            assert len(engine.workflow.nodes) == 3  # start, main, exit
            assert len(engine.workflow.edges) == 2  # start->main, main->exit
            assert engine.config_dir == tmp_dir

    def test_engine_has_agents(self):
        """Test that agents are loaded."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            self._create_minimal_config(tmp_path)

            engine = Engine.from_config_dir(tmp_dir)

            assert engine.agents is not None
            assert len(engine.agents) > 0

    def test_engine_has_tools(self):
        """Test that tools are loaded."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            self._create_minimal_config(tmp_path)

            engine = Engine.from_config_dir(tmp_dir)

            assert engine.tools is not None

    def test_engine_has_memory_stores(self):
        """Test that default memory stores are initialized."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            self._create_minimal_config(tmp_path)

            engine = Engine.from_config_dir(tmp_dir)

            assert engine.memory_stores is not None
            assert len(engine.memory_stores) > 0

    def test_engine_has_adapters(self):
        """Test that adapters are registered."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            self._create_minimal_config(tmp_path)

            engine = Engine.from_config_dir(tmp_dir)

            assert engine.adapters is not None
            assert isinstance(engine.adapters, AdapterRegistry)


class TestEngineRunMethod:
    """Test the Engine.run() stub method."""

    def _create_minimal_config(self, tmp_path):
        """Create a minimal valid config directory."""
        _write_yaml(tmp_path / "workflow.yaml", {
            "nodes": [
                {"stage_id": "start", "name": "start", "kind": "deterministic", "role": "start",
                 "context": "none", "default_start": True},
                {"stage_id": "main", "name": "main", "kind": "agent", "role": "linear",
                 "context": "global", "agent_id": "a1"},
                {"stage_id": "exit", "name": "exit", "kind": "deterministic", "role": "exit",
                 "context": "none"}
            ],
            "edges": [
                {"from_node_id": "start", "to_node_id": "main"},
                {"from_node_id": "main", "to_node_id": "exit"}
            ]
        })
        _write_yaml(tmp_path / "agents.yaml", {
            "agents": [{"id": "a1", "kind": "agent",
                       "llm": "anthropic/claude-3-5-sonnet"}]
        })
        _write_yaml(tmp_path / "tools.yaml", {"tools": []})

    def test_engine_run_returns_stub(self):
        """Test run() returns proper initialization stub."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            self._create_minimal_config(tmp_path)

            engine = Engine.from_config_dir(tmp_dir)
            result = engine.run({"test": "input"})

            assert result is not None
            assert isinstance(result, dict)
            assert result["status"] == "initialized"
            assert result["dag_valid"] is True
            assert "start_node" in result
            assert "message" in result

    def test_engine_run_with_dict_input(self):
        """Test run() accepts dict input."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            self._create_minimal_config(tmp_path)

            engine = Engine.from_config_dir(tmp_dir)
            result = engine.run({"key": "value", "nested": {"inner": "data"}})

            assert result["status"] == "initialized"

    def test_engine_run_with_string_input(self):
        """Test run() accepts string input."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            self._create_minimal_config(tmp_path)

            engine = Engine.from_config_dir(tmp_dir)
            result = engine.run("test input")

            assert result["status"] == "initialized"

    def test_engine_run_with_number_input(self):
        """Test run() accepts number input."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            self._create_minimal_config(tmp_path)

            engine = Engine.from_config_dir(tmp_dir)
            result = engine.run(42)

            assert result["status"] == "initialized"

    def test_engine_run_with_list_input(self):
        """Test run() accepts list input."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            self._create_minimal_config(tmp_path)

            engine = Engine.from_config_dir(tmp_dir)
            result = engine.run([1, 2, 3])

            assert result["status"] == "initialized"

    def test_engine_run_validates_serializable(self):
        """Test run() rejects non-JSON-serializable input."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            self._create_minimal_config(tmp_path)

            engine = Engine.from_config_dir(tmp_dir)

            # Create a non-serializable object
            class CustomObject:
                pass

            with pytest.raises(ValueError, match="JSON-serializable"):
                engine.run(CustomObject())


class TestMissingManifests:
    """Test error handling for missing required manifests."""

    def test_missing_workflow_manifest(self):
        """Test missing workflow.yaml raises ManifestLoadError."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create agents and tools but not workflow
            _write_yaml(Path(tmp_dir) / "agents.yaml", {"agents": []})
            _write_yaml(Path(tmp_dir) / "tools.yaml", {"tools": []})

            with pytest.raises(ManifestLoadError) as exc_info:
                Engine.from_config_dir(tmp_dir)

            assert "workflow.yaml" in str(exc_info.value)

    def test_missing_agents_manifest(self):
        """Test missing agents.yaml raises ManifestLoadError."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create workflow and tools but not agents
            _write_yaml(Path(tmp_dir) / "workflow.yaml", {
                "nodes": [
                    {"id": "start", "kind": "deterministic", "role": "start",
                     "context": "none", "default_start": True},
                    {"id": "exit", "kind": "deterministic", "role": "exit",
                     "context": "none"}
                ],
                "edges": [{"from": "start", "to": "exit"}]
            })
            _write_yaml(Path(tmp_dir) / "tools.yaml", {"tools": []})

            with pytest.raises(ManifestLoadError) as exc_info:
                Engine.from_config_dir(tmp_dir)

            assert "agents.yaml" in str(exc_info.value)

    def test_missing_tools_manifest(self):
        """Test missing tools.yaml raises ManifestLoadError."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create workflow and agents but not tools
            _write_yaml(Path(tmp_dir) / "workflow.yaml", {
                "nodes": [
                    {"id": "start", "kind": "deterministic", "role": "start",
                     "context": "none", "default_start": True},
                    {"id": "exit", "kind": "deterministic", "role": "exit",
                     "context": "none"}
                ],
                "edges": [{"from": "start", "to": "exit"}]
            })
            _write_yaml(Path(tmp_dir) / "agents.yaml", {"agents": []})

            with pytest.raises(ManifestLoadError) as exc_info:
                Engine.from_config_dir(tmp_dir)

            assert "tools.yaml" in str(exc_info.value)


class TestInvalidYAML:
    """Test error handling for malformed YAML."""

    def test_invalid_yaml_in_workflow(self):
        """Test malformed YAML in workflow.yaml raises ManifestLoadError."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            # Write invalid YAML
            (tmp_path / "workflow.yaml").write_text("invalid: yaml: content: [")
            _write_yaml(tmp_path / "agents.yaml", {"agents": []})
            _write_yaml(tmp_path / "tools.yaml", {"tools": []})

            with pytest.raises(ManifestLoadError) as exc_info:
                Engine.from_config_dir(tmp_dir)

            assert "workflow.yaml" in str(exc_info.value)

    def test_invalid_yaml_in_agents(self):
        """Test malformed YAML in agents.yaml raises ManifestLoadError."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            _write_yaml(tmp_path / "workflow.yaml", {
                "nodes": [
                    {"id": "start", "kind": "deterministic", "role": "start",
                     "context": "none", "default_start": True},
                    {"id": "exit", "kind": "deterministic", "role": "exit",
                     "context": "none"}
                ],
                "edges": [{"from": "start", "to": "exit"}]
            })
            # Write invalid YAML
            (tmp_path / "agents.yaml").write_text("{ invalid yaml")
            _write_yaml(tmp_path / "tools.yaml", {"tools": []})

            with pytest.raises(ManifestLoadError) as exc_info:
                Engine.from_config_dir(tmp_dir)

            assert "agents.yaml" in str(exc_info.value)

    def test_invalid_yaml_in_tools(self):
        """Test malformed YAML in tools.yaml raises ManifestLoadError."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            _write_yaml(tmp_path / "workflow.yaml", {
                "nodes": [
                    {"id": "start", "kind": "deterministic", "role": "start",
                     "context": "none", "default_start": True},
                    {"id": "exit", "kind": "deterministic", "role": "exit",
                     "context": "none"}
                ],
                "edges": [{"from": "start", "to": "exit"}]
            })
            _write_yaml(tmp_path / "agents.yaml", {"agents": []})
            # Write invalid YAML
            (tmp_path / "tools.yaml").write_text("@invalid: [yaml")

            with pytest.raises(ManifestLoadError) as exc_info:
                Engine.from_config_dir(tmp_dir)

            assert "tools.yaml" in str(exc_info.value)


class TestSchemaValidationErrors:
    """Test schema validation errors in manifest data."""

    def test_missing_required_node_field(self):
        """Test invalid node data raises SchemaValidationError."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            # Node missing 'role' field
            _write_yaml(tmp_path / "workflow.yaml", {
                "nodes": [
                    {"id": "start", "kind": "deterministic",
                     "context": "none", "default_start": True}
                ],
                "edges": []
            })
            _write_yaml(tmp_path / "agents.yaml", {"agents": []})
            _write_yaml(tmp_path / "tools.yaml", {"tools": []})

            with pytest.raises((SchemaValidationError, ValueError)):
                Engine.from_config_dir(tmp_dir)

    def test_invalid_node_role(self):
        """Test invalid node role raises SchemaValidationError."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            # Node with invalid role
            _write_yaml(tmp_path / "workflow.yaml", {
                "nodes": [
                    {"id": "start", "kind": "deterministic", "role": "invalid_role",
                     "context": "none", "default_start": True},
                    {"id": "exit", "kind": "deterministic", "role": "exit",
                     "context": "none"}
                ],
                "edges": [{"from": "start", "to": "exit"}]
            })
            _write_yaml(tmp_path / "agents.yaml", {"agents": []})
            _write_yaml(tmp_path / "tools.yaml", {"tools": []})

            with pytest.raises((SchemaValidationError, ValueError)):
                Engine.from_config_dir(tmp_dir)


class TestDAGValidationErrors:
    """Test DAG validation errors."""

    def test_cycle_in_dag(self):
        """Test cycle in DAG raises DAGValidationError."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            # Create a cycle: start -> main -> start
            _write_yaml(tmp_path / "workflow.yaml", {
                "nodes": [
                    {"stage_id": "start", "name": "start", "kind": "deterministic", "role": "start",
                     "context": "none", "default_start": True},
                    {"stage_id": "main", "name": "main", "kind": "agent", "role": "linear",
                     "context": "global", "agent_id": "a1"},
                    {"stage_id": "exit", "name": "exit", "kind": "deterministic", "role": "exit",
                     "context": "none"}
                ],
                "edges": [
                    {"from_node_id": "start", "to_node_id": "main"},
                    {"from_node_id": "main", "to_node_id": "start"},  # Cycle!
                    {"from_node_id": "main", "to_node_id": "exit"}
                ]
            })
            _write_yaml(tmp_path / "agents.yaml", {
                "agents": [{"id": "a1", "kind": "agent",
                           "llm": "anthropic/claude-3-5-sonnet"}]
            })
            _write_yaml(tmp_path / "tools.yaml", {"tools": []})

            with pytest.raises(DAGValidationError) as exc_info:
                Engine.from_config_dir(tmp_dir)

            assert "Cycle" in str(exc_info.value) or "cycle" in str(exc_info.value).lower()

    def test_multiple_default_start_nodes(self):
        """Test multiple default start nodes raises DAGValidationError."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            # Two nodes marked as default_start
            _write_yaml(tmp_path / "workflow.yaml", {
                "nodes": [
                    {"stage_id": "start1", "name": "start1", "kind": "deterministic", "role": "start",
                     "context": "none", "default_start": True},
                    {"stage_id": "start2", "name": "start2", "kind": "deterministic", "role": "start",
                     "context": "none", "default_start": True},
                    {"stage_id": "exit", "name": "exit", "kind": "deterministic", "role": "exit",
                     "context": "none"}
                ],
                "edges": [
                    {"from_node_id": "start1", "to_node_id": "exit"},
                    {"from_node_id": "start2", "to_node_id": "exit"}
                ]
            })
            _write_yaml(tmp_path / "agents.yaml", {"agents": []})
            _write_yaml(tmp_path / "tools.yaml", {"tools": []})

            with pytest.raises(DAGValidationError) as exc_info:
                Engine.from_config_dir(tmp_dir)

            assert "start" in str(exc_info.value).lower()

    def test_no_default_start_node(self):
        """Test missing default start node raises DAGValidationError."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            # START node but no default_start=True
            _write_yaml(tmp_path / "workflow.yaml", {
                "nodes": [
                    {"stage_id": "start", "name": "start", "kind": "deterministic", "role": "start",
                     "context": "none", "default_start": False},
                    {"stage_id": "exit", "name": "exit", "kind": "deterministic", "role": "exit",
                     "context": "none"}
                ],
                "edges": [{"from_node_id": "start", "to_node_id": "exit"}]
            })
            _write_yaml(tmp_path / "agents.yaml", {"agents": []})
            _write_yaml(tmp_path / "tools.yaml", {"tools": []})

            with pytest.raises(DAGValidationError) as exc_info:
                Engine.from_config_dir(tmp_dir)

            assert "start" in str(exc_info.value).lower()


class TestOptionalManifests:
    """Test handling of optional manifest files."""

    def test_optional_manifests_default(self):
        """Test missing memory.yaml uses defaults."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            _write_yaml(tmp_path / "workflow.yaml", {
                "nodes": [
                    {"stage_id": "start", "name": "start", "kind": "deterministic", "role": "start",
                     "context": "none", "default_start": True},
                    {"stage_id": "exit", "name": "exit", "kind": "deterministic", "role": "exit",
                     "context": "none"}
                ],
                "edges": [{"from_node_id": "start", "to_node_id": "exit"}]
            })
            _write_yaml(tmp_path / "agents.yaml", {"agents": []})
            _write_yaml(tmp_path / "tools.yaml", {"tools": []})
            # Note: NOT creating memory.yaml

            engine = Engine.from_config_dir(tmp_dir)

            assert engine is not None
            assert engine.memory_stores is not None
            # Should have default memory stores
            assert len(engine.memory_stores) > 0

    def test_optional_plugins_manifest(self):
        """Test missing plugins.yaml is handled gracefully."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            _write_yaml(tmp_path / "workflow.yaml", {
                "nodes": [
                    {"stage_id": "start", "name": "start", "kind": "deterministic", "role": "start",
                     "context": "none", "default_start": True},
                    {"stage_id": "exit", "name": "exit", "kind": "deterministic", "role": "exit",
                     "context": "none"}
                ],
                "edges": [{"from_node_id": "start", "to_node_id": "exit"}]
            })
            _write_yaml(tmp_path / "agents.yaml", {"agents": []})
            _write_yaml(tmp_path / "tools.yaml", {"tools": []})
            # Note: NOT creating plugins.yaml

            engine = Engine.from_config_dir(tmp_dir)

            assert engine is not None
            assert engine.plugins is not None
            assert isinstance(engine.plugins, list)


class TestAdapterRegistration:
    """Test tools and LLM providers are registered."""

    def _create_minimal_config(self, tmp_path):
        """Create a minimal valid config directory."""
        _write_yaml(tmp_path / "workflow.yaml", {
            "nodes": [
                {"stage_id": "start", "name": "start", "kind": "deterministic", "role": "start",
                 "context": "none", "default_start": True},
                {"stage_id": "main", "name": "main", "kind": "agent", "role": "linear",
                 "context": "global", "agent_id": "a1"},
                {"stage_id": "exit", "name": "exit", "kind": "deterministic", "role": "exit",
                 "context": "none"}
            ],
            "edges": [
                {"from_node_id": "start", "to_node_id": "main"},
                {"from_node_id": "main", "to_node_id": "exit"}
            ]
        })
        _write_yaml(tmp_path / "agents.yaml", {
            "agents": [{"id": "a1", "kind": "agent",
                       "llm": "anthropic/claude-3-5-sonnet"}]
        })
        _write_yaml(tmp_path / "tools.yaml", {"tools": []})

    def test_adapter_registration(self):
        """Test tools and LLM providers registered."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            self._create_minimal_config(tmp_path)

            engine = Engine.from_config_dir(tmp_dir)

            assert engine.adapters is not None
            # Check that adapters were registered
            assert len(engine.adapters.llm_providers) > 0 or len(engine.adapters.tools) > 0

    def test_llm_providers_registered(self):
        """Test LLM providers are registered from agents."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            self._create_minimal_config(tmp_path)

            engine = Engine.from_config_dir(tmp_dir)

            # Should have at least one LLM provider from agents
            assert len(engine.adapters.llm_providers) > 0

    def test_tools_registered(self):
        """Test tools are registered from tools manifest."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            # Create config with a tool
            _write_yaml(tmp_path / "workflow.yaml", {
                "nodes": [
                    {"stage_id": "start", "name": "start", "kind": "deterministic", "role": "start",
                     "context": "none", "default_start": True},
                    {"stage_id": "exit", "name": "exit", "kind": "deterministic", "role": "exit",
                     "context": "none"}
                ],
                "edges": [{"from_node_id": "start", "to_node_id": "exit"}]
            })
            _write_yaml(tmp_path / "agents.yaml", {"agents": []})
            _write_yaml(tmp_path / "tools.yaml", {
                "tools": [{
                    "id": "t1", "type": "filesystem", "entrypoint": "test",
                    "permissions": {
                        "allow_network": False,
                        "allow_shell": False,
                        "root": False
                    }
                }]
            })

            engine = Engine.from_config_dir(tmp_dir)

            # Should have at least one tool registered
            assert len(engine.adapters.tools) > 0


class TestSchemaLoading:
    """Test schemas are loaded from schemas/ directory."""

    def test_schemas_loaded(self):
        """Test schemas loaded from schemas/ directory."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            _write_yaml(tmp_path / "workflow.yaml", {
                "nodes": [
                    {"stage_id": "start", "name": "start", "kind": "deterministic", "role": "start",
                     "context": "none", "default_start": True},
                    {"stage_id": "exit", "name": "exit", "kind": "deterministic", "role": "exit",
                     "context": "none"}
                ],
                "edges": [{"from_node_id": "start", "to_node_id": "exit"}]
            })
            _write_yaml(tmp_path / "agents.yaml", {"agents": []})
            _write_yaml(tmp_path / "tools.yaml", {"tools": []})

            # Create schemas directory with a test schema
            schemas_dir = tmp_path / "schemas"
            schemas_dir.mkdir()
            _write_json(schemas_dir / "test_schema.json", {
                "type": "object",
                "properties": {"test": {"type": "string"}}
            })

            engine = Engine.from_config_dir(tmp_dir)

            assert engine.schemas is not None
            assert isinstance(engine.schemas, dict)
            # Should have loaded the test schema
            assert "test_schema" in engine.schemas

    def test_schemas_dict_when_no_directory(self):
        """Test empty schemas dict when no schemas/ directory exists."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            _write_yaml(tmp_path / "workflow.yaml", {
                "nodes": [
                    {"stage_id": "start", "name": "start", "kind": "deterministic", "role": "start",
                     "context": "none", "default_start": True},
                    {"stage_id": "exit", "name": "exit", "kind": "deterministic", "role": "exit",
                     "context": "none"}
                ],
                "edges": [{"from_node_id": "start", "to_node_id": "exit"}]
            })
            _write_yaml(tmp_path / "agents.yaml", {"agents": []})
            _write_yaml(tmp_path / "tools.yaml", {"tools": []})
            # Don't create schemas directory

            engine = Engine.from_config_dir(tmp_dir)

            assert engine.schemas is not None
            assert isinstance(engine.schemas, dict)
            assert len(engine.schemas) == 0


class TestContextProfileValidation:
    """Test context profile validation."""

    def _create_minimal_config(self, tmp_path):
        """Create a minimal valid config directory."""
        _write_yaml(tmp_path / "workflow.yaml", {
            "nodes": [
                {"stage_id": "start", "name": "start", "kind": "deterministic", "role": "start",
                 "context": "none", "default_start": True},
                {"stage_id": "main", "name": "main", "kind": "agent", "role": "linear",
                 "context": "global", "agent_id": "a1"},
                {"stage_id": "exit", "name": "exit", "kind": "deterministic", "role": "exit",
                 "context": "none"}
            ],
            "edges": [
                {"from_node_id": "start", "to_node_id": "main"},
                {"from_node_id": "main", "to_node_id": "exit"}
            ]
        })
        _write_yaml(tmp_path / "agents.yaml", {
            "agents": [{"id": "a1", "kind": "agent",
                       "llm": "anthropic/claude-3-5-sonnet"}]
        })
        _write_yaml(tmp_path / "tools.yaml", {"tools": []})

    def test_context_profile_with_global_context(self):
        """Test nodes with context='global' are valid."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            self._create_minimal_config(tmp_path)

            engine = Engine.from_config_dir(tmp_dir)

            assert engine is not None
            assert engine.context_profiles is not None

    def test_context_profile_with_none_context(self):
        """Test nodes with context='none' are valid."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            self._create_minimal_config(tmp_path)

            engine = Engine.from_config_dir(tmp_dir)

            # The config has nodes with context='none'
            assert engine is not None
            assert engine.workflow is not None

    def test_context_profiles_initialized(self):
        """Test context profiles are initialized."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            self._create_minimal_config(tmp_path)

            engine = Engine.from_config_dir(tmp_dir)

            assert engine.context_profiles is not None
            assert isinstance(engine.context_profiles, dict)


class TestEngineAttributes:
    """Test Engine object attributes after initialization."""

    def _create_minimal_config(self, tmp_path):
        """Create a minimal valid config directory."""
        _write_yaml(tmp_path / "workflow.yaml", {
            "nodes": [
                {"stage_id": "start", "name": "start", "kind": "deterministic", "role": "start",
                 "context": "none", "default_start": True},
                {"stage_id": "main", "name": "main", "kind": "agent", "role": "linear",
                 "context": "global", "agent_id": "a1"},
                {"stage_id": "exit", "name": "exit", "kind": "deterministic", "role": "exit",
                 "context": "none"}
            ],
            "edges": [
                {"from_node_id": "start", "to_node_id": "main"},
                {"from_node_id": "main", "to_node_id": "exit"}
            ]
        })
        _write_yaml(tmp_path / "agents.yaml", {
            "agents": [{"id": "a1", "kind": "agent",
                       "llm": "anthropic/claude-3-5-sonnet"}]
        })
        _write_yaml(tmp_path / "tools.yaml", {"tools": []})

    def test_engine_config_dir_attribute(self):
        """Test Engine has config_dir attribute."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            self._create_minimal_config(tmp_path)

            engine = Engine.from_config_dir(tmp_dir)

            assert engine.config_dir == tmp_dir

    def test_engine_workflow_attribute(self):
        """Test Engine has workflow attribute."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            self._create_minimal_config(tmp_path)

            engine = Engine.from_config_dir(tmp_dir)

            assert hasattr(engine, 'workflow')
            assert engine.workflow is not None

    def test_engine_agents_attribute(self):
        """Test Engine has agents attribute."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            self._create_minimal_config(tmp_path)

            engine = Engine.from_config_dir(tmp_dir)

            assert hasattr(engine, 'agents')
            assert engine.agents is not None

    def test_engine_tools_attribute(self):
        """Test Engine has tools attribute."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            self._create_minimal_config(tmp_path)

            engine = Engine.from_config_dir(tmp_dir)

            assert hasattr(engine, 'tools')
            assert engine.tools is not None

    def test_engine_schemas_attribute(self):
        """Test Engine has schemas attribute."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            self._create_minimal_config(tmp_path)

            engine = Engine.from_config_dir(tmp_dir)

            assert hasattr(engine, 'schemas')
            assert engine.schemas is not None

    def test_engine_memory_stores_attribute(self):
        """Test Engine has memory_stores attribute."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            self._create_minimal_config(tmp_path)

            engine = Engine.from_config_dir(tmp_dir)

            assert hasattr(engine, 'memory_stores')
            assert engine.memory_stores is not None

    def test_engine_context_profiles_attribute(self):
        """Test Engine has context_profiles attribute."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            self._create_minimal_config(tmp_path)

            engine = Engine.from_config_dir(tmp_dir)

            assert hasattr(engine, 'context_profiles')
            assert engine.context_profiles is not None

    def test_engine_adapters_attribute(self):
        """Test Engine has adapters attribute."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            self._create_minimal_config(tmp_path)

            engine = Engine.from_config_dir(tmp_dir)

            assert hasattr(engine, 'adapters')
            assert engine.adapters is not None

    def test_engine_plugins_attribute(self):
        """Test Engine has plugins attribute."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            self._create_minimal_config(tmp_path)

            engine = Engine.from_config_dir(tmp_dir)

            assert hasattr(engine, 'plugins')
            assert engine.plugins is not None


class TestEngineInitializationSequence:
    """Test the full initialization sequence per AGENT_ENGINE_SPEC §8."""

    def _create_minimal_config(self, tmp_path):
        """Create a minimal valid config directory."""
        _write_yaml(tmp_path / "workflow.yaml", {
            "nodes": [
                {"stage_id": "start", "name": "start", "kind": "deterministic", "role": "start",
                 "context": "none", "default_start": True},
                {"stage_id": "main", "name": "main", "kind": "agent", "role": "linear",
                 "context": "global", "agent_id": "a1"},
                {"stage_id": "exit", "name": "exit", "kind": "deterministic", "role": "exit",
                 "context": "none"}
            ],
            "edges": [
                {"from_node_id": "start", "to_node_id": "main"},
                {"from_node_id": "main", "to_node_id": "exit"}
            ]
        })
        _write_yaml(tmp_path / "agents.yaml", {
            "agents": [{"id": "a1", "kind": "agent",
                       "llm": "anthropic/claude-3-5-sonnet"}]
        })
        _write_yaml(tmp_path / "tools.yaml", {"tools": []})

    def test_initialization_sequence_completes(self):
        """Test full initialization sequence completes without error."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            self._create_minimal_config(tmp_path)

            # Should not raise any exceptions
            engine = Engine.from_config_dir(tmp_dir)

            assert engine is not None
            # Verify all steps completed
            assert engine.workflow is not None  # Step 3: DAG constructed
            assert engine.adapters is not None  # Step 6: Adapters registered
            assert engine.memory_stores is not None  # Step 5: Memory stores initialized

    def test_default_start_node_accessible(self):
        """Test we can get the default start node."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            self._create_minimal_config(tmp_path)

            engine = Engine.from_config_dir(tmp_dir)

            start_node = engine.workflow.get_default_start_node()

            assert start_node is not None
            assert start_node.stage_id == "start"

    def test_outbound_edges_accessible(self):
        """Test we can get outbound edges from a node."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            self._create_minimal_config(tmp_path)

            engine = Engine.from_config_dir(tmp_dir)

            start_node = engine.workflow.get_default_start_node()
            outbound = engine.workflow.get_outbound_edges(start_node.stage_id)

            assert outbound is not None
            assert isinstance(outbound, list)
            assert len(outbound) > 0
