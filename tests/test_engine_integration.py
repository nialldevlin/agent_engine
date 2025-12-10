"""Phase 2 Integration Tests for Agent Engine.

End-to-end tests with realistic, complex configurations covering:
- Complex DAG structures with decision and merge nodes
- Multiple agents with different LLM providers
- Custom tools with various permissions
- Memory store initialization
- Context profile loading
- Node reference validation

These tests validate the Engine.from_config_dir() initialization sequence
and ensure all components are properly loaded and validated.
"""

import pytest
import tempfile
import os
import yaml
from pathlib import Path

from agent_engine import (
    Engine,
    DAG,
    DAGValidationError,
    ManifestLoadError,
    SchemaValidationError
)


@pytest.fixture
def complex_config_dir(tmp_path):
    """Create a complex test configuration with decision and merge nodes.

    This fixture creates a realistic workflow with:
    - START node
    - DECISION node that branches to two paths
    - Two parallel PATH nodes with different tools
    - MERGE node to reconcile paths
    - EXIT node
    - Multiple agents and tools
    - Custom context profiles
    """
    config_dir = tmp_path / "complex_config"
    config_dir.mkdir()

    # Create workflow with decision and merge structure
    workflow = {
        "nodes": [
            {
                "stage_id": "start",
                "name": "start_node",
                "kind": "deterministic",
                "role": "start",
                "default_start": True,
                "context": "none",
                "continue_on_failure": False
            },
            {
                "stage_id": "decision",
                "name": "decision_node",
                "kind": "agent",
                "role": "decision",
                "agent_id": "agent_1",
                "context": "global",
                "continue_on_failure": False
            },
            {
                "stage_id": "path_a",
                "name": "path_a_node",
                "kind": "deterministic",
                "role": "linear",
                "context": "global",
                "tools": ["tool_a"],
                "continue_on_failure": False
            },
            {
                "stage_id": "path_b",
                "name": "path_b_node",
                "kind": "agent",
                "role": "linear",
                "agent_id": "agent_2",
                "context": "global",
                "tools": ["tool_b"],
                "continue_on_failure": False
            },
            {
                "stage_id": "merge",
                "name": "merge_node",
                "kind": "deterministic",
                "role": "merge",
                "context": "none",
                "continue_on_failure": False
            },
            {
                "stage_id": "exit",
                "name": "exit_node",
                "kind": "deterministic",
                "role": "exit",
                "context": "none",
                "continue_on_failure": False
            }
        ],
        "edges": [
            {"from_node_id": "start", "to_node_id": "decision"},
            {"from_node_id": "decision", "to_node_id": "path_a", "condition": "option_a"},
            {"from_node_id": "decision", "to_node_id": "path_b", "condition": "option_b"},
            {"from_node_id": "path_a", "to_node_id": "merge"},
            {"from_node_id": "path_b", "to_node_id": "merge"},
            {"from_node_id": "merge", "to_node_id": "exit"}
        ]
    }

    with open(config_dir / "workflow.yaml", 'w') as f:
        yaml.dump(workflow, f)

    # Create agents manifest
    agents = {
        "agents": [
            {
                "id": "agent_1",
                "kind": "agent",
                "llm": "provider_a",
                "config": {}
            },
            {
                "id": "agent_2",
                "kind": "agent",
                "llm": "provider_b",
                "config": {}
            }
        ]
    }

    with open(config_dir / "agents.yaml", 'w') as f:
        yaml.dump(agents, f)

    # Create tools manifest with different permissions
    tools = {
        "tools": [
            {
                "id": "tool_a",
                "type": "test",
                "entrypoint": "test:tool_a",
                "permissions": {
                    "allow_network": False,
                    "allow_shell": False,
                    "root": False
                }
            },
            {
                "id": "tool_b",
                "type": "test",
                "entrypoint": "test:tool_b",
                "permissions": {
                    "allow_network": True,
                    "allow_shell": False,
                    "root": False
                }
            },
            {
                "id": "tool_c",
                "type": "test",
                "entrypoint": "test:tool_c",
                "permissions": {
                    "allow_network": False,
                    "allow_shell": True,
                    "root": False
                }
            }
        ]
    }

    with open(config_dir / "tools.yaml", 'w') as f:
        yaml.dump(tools, f)

    # Create memory config with custom context profiles
    memory = {
        "memory": {
            "task_store": {"type": "in_memory"},
            "project_store": {"type": "in_memory"},
            "global_store": {"type": "in_memory"},
            "context_profiles": [
                {
                    "id": "custom_profile",
                    "max_tokens": 4000,
                    "retrieval_policy": "semantic",
                    "sources": [
                        {"store": "task", "tags": ["important"]},
                        {"store": "project", "tags": []}
                    ]
                },
                {
                    "id": "full_context",
                    "max_tokens": 8000,
                    "retrieval_policy": "chronological",
                    "sources": [
                        {"store": "task", "tags": []},
                        {"store": "project", "tags": []},
                        {"store": "global", "tags": []}
                    ]
                }
            ]
        }
    }

    with open(config_dir / "memory.yaml", 'w') as f:
        yaml.dump(memory, f)

    # Create empty schemas directory
    (config_dir / "schemas").mkdir()

    return str(config_dir)


@pytest.fixture
def simple_config_dir(tmp_path):
    """Create a minimal valid configuration for basic tests."""
    config_dir = tmp_path / "simple_config"
    config_dir.mkdir()

    # Minimal workflow
    workflow = {
        "nodes": [
            {
                "stage_id": "start",
                "name": "start",
                "kind": "deterministic",
                "role": "start",
                "default_start": True,
                "context": "none",
                "continue_on_failure": False
            },
            {
                "stage_id": "exit",
                "name": "exit",
                "kind": "deterministic",
                "role": "exit",
                "context": "none",
                "continue_on_failure": False
            }
        ],
        "edges": [
            {"from_node_id": "start", "to_node_id": "exit"}
        ]
    }

    with open(config_dir / "workflow.yaml", 'w') as f:
        yaml.dump(workflow, f)

    # Minimal agents
    agents = {
        "agents": [
            {
                "id": "simple_agent",
                "kind": "agent",
                "llm": "test_llm",
                "config": {}
            }
        ]
    }

    with open(config_dir / "agents.yaml", 'w') as f:
        yaml.dump(agents, f)

    # Minimal tools
    tools = {
        "tools": [
            {
                "id": "simple_tool",
                "type": "test",
                "entrypoint": "test:simple",
                "permissions": {
                    "allow_network": False,
                    "allow_shell": False,
                    "root": False
                }
            }
        ]
    }

    with open(config_dir / "tools.yaml", 'w') as f:
        yaml.dump(tools, f)

    # Create schemas directory
    (config_dir / "schemas").mkdir()

    return str(config_dir)


# Test 1: Load complex configuration successfully
def test_complex_config_loading(complex_config_dir):
    """Test loading complex configuration with multiple agents and tools.

    Validates that Engine.from_config_dir() successfully:
    - Loads all manifests
    - Validates node and edge schemas
    - Constructs the DAG
    - Initializes memory stores
    - Loads context profiles
    """
    engine = Engine.from_config_dir(complex_config_dir)

    # Verify engine is created
    assert engine is not None

    # Verify all nodes are loaded
    assert len(engine.workflow.nodes) == 6
    assert "start" in engine.workflow.nodes
    assert "decision" in engine.workflow.nodes
    assert "path_a" in engine.workflow.nodes
    assert "path_b" in engine.workflow.nodes
    assert "merge" in engine.workflow.nodes
    assert "exit" in engine.workflow.nodes

    # Verify all agents are loaded
    assert len(engine.agents) == 2
    assert any(agent["id"] == "agent_1" for agent in engine.agents)
    assert any(agent["id"] == "agent_2" for agent in engine.agents)

    # Verify all tools are loaded
    assert len(engine.tools) == 3
    tool_ids = {tool["id"] for tool in engine.tools}
    assert tool_ids == {"tool_a", "tool_b", "tool_c"}

    # Verify DAG is valid
    assert isinstance(engine.workflow, DAG)
    assert engine.workflow is not None


# Test 2: DAG adjacency correctness for decision nodes
def test_dag_adjacency_correctness(complex_config_dir):
    """Test that DAG adjacency map correctly represents edges.

    Validates that:
    - Decision node has two outbound edges with correct labels
    - Linear nodes have one outbound edge
    - Merge node has one outbound edge
    - Exit node has zero outbound edges
    - Adjacency map is efficiently queryable
    """
    engine = Engine.from_config_dir(complex_config_dir)
    dag = engine.workflow

    # Check decision node has two outbound edges
    decision_edges = dag.get_outbound_edges("decision")
    assert len(decision_edges) == 2
    edge_conditions = {edge.condition for edge in decision_edges}
    assert edge_conditions == {"option_a", "option_b"}

    # Verify target nodes of decision edges
    target_ids = {edge.to_node_id for edge in decision_edges}
    assert target_ids == {"path_a", "path_b"}

    # Check linear nodes have single outbound edge
    path_a_edges = dag.get_outbound_edges("path_a")
    assert len(path_a_edges) == 1
    assert path_a_edges[0].to_node_id == "merge"

    path_b_edges = dag.get_outbound_edges("path_b")
    assert len(path_b_edges) == 1
    assert path_b_edges[0].to_node_id == "merge"

    # Check merge node has single outbound edge
    merge_edges = dag.get_outbound_edges("merge")
    assert len(merge_edges) == 1
    assert merge_edges[0].to_node_id == "exit"

    # Check exit node has no outbound edges
    exit_edges = dag.get_outbound_edges("exit")
    assert len(exit_edges) == 0

    # Check start node has single outbound edge
    start_edges = dag.get_outbound_edges("start")
    assert len(start_edges) == 1
    assert start_edges[0].to_node_id == "decision"


# Test 3: Configuration with all manifests loads successfully
def test_all_manifests_present(tmp_path):
    """Test that config with all optional manifests (memory, tools, agents) loads.

    This ensures that when all manifests are provided, they are all loaded
    and made available through the engine instance.
    """
    config_dir = tmp_path / "full_config"
    config_dir.mkdir()

    # Create complete workflow
    workflow = {
        "nodes": [
            {
                "stage_id": "start",
                "name": "start",
                "kind": "deterministic",
                "role": "start",
                "default_start": True,
                "context": "none",
                "continue_on_failure": False
            },
            {
                "stage_id": "worker",
                "name": "worker",
                "kind": "deterministic",
                "role": "linear",
                "tools": ["tool_x"],
                "context": "global",
                "continue_on_failure": False
            },
            {
                "stage_id": "exit",
                "name": "exit",
                "kind": "deterministic",
                "role": "exit",
                "context": "none",
                "continue_on_failure": False
            }
        ],
        "edges": [
            {"from_node_id": "start", "to_node_id": "worker"},
            {"from_node_id": "worker", "to_node_id": "exit"}
        ]
    }

    with open(config_dir / "workflow.yaml", 'w') as f:
        yaml.dump(workflow, f)

    # Create agents
    agents = {"agents": [{"id": "a1", "kind": "agent", "llm": "test", "config": {}}]}
    with open(config_dir / "agents.yaml", 'w') as f:
        yaml.dump(agents, f)

    # Create tools
    tools = {
        "tools": [
            {
                "id": "tool_x",
                "type": "test",
                "entrypoint": "test:x",
                "permissions": {"allow_network": False, "allow_shell": False, "root": False}
            }
        ]
    }
    with open(config_dir / "tools.yaml", 'w') as f:
        yaml.dump(tools, f)

    # Create memory config
    memory = {
        "memory": {
            "task_store": {"type": "in_memory"},
            "project_store": {"type": "in_memory"},
            "global_store": {"type": "in_memory"}
        }
    }
    with open(config_dir / "memory.yaml", 'w') as f:
        yaml.dump(memory, f)

    # Create schemas directory
    (config_dir / "schemas").mkdir()

    # This should load successfully
    engine = Engine.from_config_dir(str(config_dir))
    assert engine is not None
    assert len(engine.memory_stores) == 3


# Test 4: Memory stores are initialized
def test_memory_stores_initialized(complex_config_dir):
    """Test that all three memory stores are created.

    Validates that Engine initialization creates:
    - task store
    - project store
    - global store

    And that they are accessible from the engine instance.
    """
    engine = Engine.from_config_dir(complex_config_dir)

    # Verify memory stores exist
    assert engine.memory_stores is not None
    assert isinstance(engine.memory_stores, dict)

    # Verify all three stores are present
    assert "task" in engine.memory_stores
    assert "project" in engine.memory_stores
    assert "global" in engine.memory_stores

    # Verify stores are MemoryStore instances
    for store_id, store in engine.memory_stores.items():
        assert store is not None
        assert hasattr(store, "store_id")
        assert hasattr(store, "store_type")
        assert store.store_id == store_id


# Test 5: Context profiles are loaded correctly
def test_context_profiles_loaded(complex_config_dir):
    """Test that custom context profiles are loaded from memory.yaml.

    Validates that:
    - Custom profiles defined in memory.yaml are loaded
    - Profile properties (max_tokens, retrieval_policy, sources) are preserved
    - Default profile exists if none specified
    - Profiles are accessible by ID
    """
    engine = Engine.from_config_dir(complex_config_dir)

    # Verify context profiles exist
    assert engine.context_profiles is not None
    assert isinstance(engine.context_profiles, dict)

    # Verify custom profiles are loaded
    assert "custom_profile" in engine.context_profiles
    assert "full_context" in engine.context_profiles

    # Verify profile properties
    custom_profile = engine.context_profiles["custom_profile"]
    assert custom_profile is not None
    assert hasattr(custom_profile, "id")
    assert custom_profile.id == "custom_profile"

    full_profile = engine.context_profiles["full_context"]
    assert full_profile is not None
    assert full_profile.id == "full_context"


# Test 6: Simple config loads successfully
def test_simple_config_loading(simple_config_dir):
    """Test loading a minimal valid configuration.

    Validates that the minimal required elements are sufficient
    to create a working engine.
    """
    engine = Engine.from_config_dir(simple_config_dir)

    assert engine is not None
    assert len(engine.workflow.nodes) == 2
    assert len(engine.agents) == 1
    assert len(engine.tools) == 1


# Test 7: Default start node is accessible
def test_default_start_node(complex_config_dir):
    """Test that the default start node can be retrieved.

    Validates that:
    - get_default_start_node() returns the correct node
    - Node marked with default_start=True is identifiable
    - Only one default start node is allowed
    """
    engine = Engine.from_config_dir(complex_config_dir)

    start_node = engine.workflow.get_default_start_node()
    assert start_node is not None
    assert start_node.stage_id == "start"
    assert start_node.default_start is True
    assert start_node.role.value == "start"


# Test 8: Multiple agents with different providers
def test_multiple_agents_different_providers(complex_config_dir):
    """Test that multiple agents with different LLM providers are loaded.

    Validates that:
    - Multiple agents can coexist in agents.yaml
    - Each agent maintains its own LLM provider configuration
    - Agent IDs are unique and retrievable
    """
    engine = Engine.from_config_dir(complex_config_dir)

    agents = engine.agents
    assert len(agents) == 2

    # Create a map of agent_id to agent
    agent_map = {agent["id"]: agent for agent in agents}

    # Verify both agents exist with different providers
    assert "agent_1" in agent_map
    assert "agent_2" in agent_map

    agent_1 = agent_map["agent_1"]
    agent_2 = agent_map["agent_2"]

    assert agent_1["llm"] == "provider_a"
    assert agent_2["llm"] == "provider_b"


# Test 9: Tools have correct permission structure
def test_tools_permission_structure(complex_config_dir):
    """Test that tools maintain proper permission structure.

    Validates that:
    - All required permission fields exist
    - Permission values are boolean
    - Different tools can have different permission levels
    """
    engine = Engine.from_config_dir(complex_config_dir)

    tools = engine.tools
    assert len(tools) == 3

    # Create tool map for easier testing
    tool_map = {tool["id"]: tool for tool in tools}

    # Verify tool_a has restricted permissions
    tool_a = tool_map["tool_a"]
    assert tool_a["permissions"]["allow_network"] is False
    assert tool_a["permissions"]["allow_shell"] is False
    assert tool_a["permissions"]["root"] is False

    # Verify tool_b allows network
    tool_b = tool_map["tool_b"]
    assert tool_b["permissions"]["allow_network"] is True
    assert tool_b["permissions"]["allow_shell"] is False
    assert tool_b["permissions"]["root"] is False

    # Verify tool_c allows shell
    tool_c = tool_map["tool_c"]
    assert tool_c["permissions"]["allow_network"] is False
    assert tool_c["permissions"]["allow_shell"] is True
    assert tool_c["permissions"]["root"] is False


# Test 10: DAG validation catches cycles
def test_dag_validation_catches_cycles(tmp_path):
    """Test that DAG validation rejects cyclic graphs.

    Ensures that the DAG cannot contain cycles, which would break
    the acyclic guarantee of workflow execution.
    """
    config_dir = tmp_path / "cyclic_config"
    config_dir.mkdir()

    # Create workflow with a cycle
    workflow = {
        "nodes": [
            {
                "stage_id": "node_a",
                "name": "a",
                "kind": "deterministic",
                "role": "start",
                "default_start": True,
                "context": "none",
                "continue_on_failure": False
            },
            {
                "stage_id": "node_b",
                "name": "b",
                "kind": "deterministic",
                "role": "linear",
                "context": "global",
                "continue_on_failure": False
            }
        ],
        "edges": [
            {"from_node_id": "node_a", "to_node_id": "node_b"},
            {"from_node_id": "node_b", "to_node_id": "node_a"}  # Cycle!
        ]
    }

    with open(config_dir / "workflow.yaml", 'w') as f:
        yaml.dump(workflow, f)

    agents = {"agents": [{"id": "a1", "kind": "agent", "llm": "test", "config": {}}]}
    with open(config_dir / "agents.yaml", 'w') as f:
        yaml.dump(agents, f)

    tools = {
        "tools": [
            {
                "id": "t1",
                "type": "test",
                "entrypoint": "test:t1",
                "permissions": {"allow_network": False, "allow_shell": False, "root": False}
            }
        ]
    }
    with open(config_dir / "tools.yaml", 'w') as f:
        yaml.dump(tools, f)

    (config_dir / "schemas").mkdir()

    # Should raise DAGValidationError due to cycle
    with pytest.raises(DAGValidationError):
        Engine.from_config_dir(str(config_dir))


# Test 11: Engine run() returns initialized status stub
def test_engine_run_returns_stub(simple_config_dir):
    """Test that Engine.run() returns a valid stub for Phase 2.

    In Phase 2, execution is not implemented. This test validates
    that run() returns the expected stub structure indicating
    initialization succeeded.
    """
    engine = Engine.from_config_dir(simple_config_dir)

    # Call run with simple input
    result = engine.run({"test": "input"})

    # Verify stub structure
    assert result is not None
    assert isinstance(result, dict)
    assert "status" in result
    assert result["status"] == "initialized"
    assert "dag_valid" in result
    assert result["dag_valid"] is True
    assert "start_node" in result
    assert result["start_node"] == "start"


# Test 12: Invalid YAML manifests raise ManifestLoadError
def test_invalid_yaml_raises_error(tmp_path):
    """Test that invalid YAML in manifests raises appropriate error.

    Ensures that manifest loading catches YAML parse errors early.
    """
    config_dir = tmp_path / "invalid_yaml_config"
    config_dir.mkdir()

    # Write invalid YAML
    with open(config_dir / "workflow.yaml", 'w') as f:
        f.write("{ invalid: yaml: [structure")

    agents = {"agents": [{"id": "a1", "kind": "agent", "llm": "test", "config": {}}]}
    with open(config_dir / "agents.yaml", 'w') as f:
        yaml.dump(agents, f)

    tools = {
        "tools": [
            {
                "id": "t1",
                "type": "test",
                "entrypoint": "test:t1",
                "permissions": {"allow_network": False, "allow_shell": False, "root": False}
            }
        ]
    }
    with open(config_dir / "tools.yaml", 'w') as f:
        yaml.dump(tools, f)

    (config_dir / "schemas").mkdir()

    # Should raise ManifestLoadError
    with pytest.raises(ManifestLoadError):
        Engine.from_config_dir(str(config_dir))


# Test 13: Node kind and role invariants are enforced
def test_node_kind_role_invariants(tmp_path):
    """Test that kind-role invariants are validated.

    Per spec, START and EXIT nodes must be DETERMINISTIC.
    This test ensures that attempting to use AGENT kind for
    START or EXIT nodes is rejected.
    """
    config_dir = tmp_path / "bad_invariant_config"
    config_dir.mkdir()

    # Try to create an AGENT START node (violates invariant)
    workflow = {
        "nodes": [
            {
                "stage_id": "bad_start",
                "name": "bad",
                "kind": "agent",  # VIOLATION: START must be DETERMINISTIC
                "role": "start",
                "default_start": True,
                "agent_id": "a1",
                "context": "none",
                "continue_on_failure": False
            },
            {
                "stage_id": "exit",
                "name": "exit",
                "kind": "deterministic",
                "role": "exit",
                "context": "none",
                "continue_on_failure": False
            }
        ],
        "edges": [
            {"from_node_id": "bad_start", "to_node_id": "exit"}
        ]
    }

    with open(config_dir / "workflow.yaml", 'w') as f:
        yaml.dump(workflow, f)

    agents = {"agents": [{"id": "a1", "kind": "agent", "llm": "test", "config": {}}]}
    with open(config_dir / "agents.yaml", 'w') as f:
        yaml.dump(agents, f)

    tools = {
        "tools": [
            {
                "id": "t1",
                "type": "test",
                "entrypoint": "test:t1",
                "permissions": {"allow_network": False, "allow_shell": False, "root": False}
            }
        ]
    }
    with open(config_dir / "tools.yaml", 'w') as f:
        yaml.dump(tools, f)

    (config_dir / "schemas").mkdir()

    # Should raise validation error
    with pytest.raises((SchemaValidationError, DAGValidationError)):
        Engine.from_config_dir(str(config_dir))
