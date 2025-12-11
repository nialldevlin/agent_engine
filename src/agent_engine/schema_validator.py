"""Schema validation functions for manifest data against Pydantic schemas.

This module provides validation functions for each manifest type (nodes, edges, agents,
tools, memory configurations). All validation errors are wrapped in SchemaValidationError
with clear field paths for debugging.
"""

from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from .dag import DAG
from .exceptions import SchemaValidationError
from .schemas.memory import ContextProfile, ContextProfileSource
from .schemas.stage import Node, NodeRole, NodeKind
from .schemas.workflow import Edge


def validate_nodes(nodes_data: List[Dict], file_name: str = "workflow.yaml") -> Dict[str, Node]:
    """Validate node data and return dict of node_id -> Node.

    Args:
        nodes_data: List of node dictionaries to validate.
        file_name: Name of the file being validated (for error reporting).

    Returns:
        Dictionary mapping node IDs to validated Node objects.

    Raises:
        SchemaValidationError: If validation fails for any node.
    """
    nodes = {}
    for i, node_dict in enumerate(nodes_data):
        try:
            node = Node(**node_dict)
            nodes[node.stage_id] = node
        except ValidationError as e:
            field_path = f"nodes[{i}]"
            raise SchemaValidationError(file_name, field_path, str(e))
        except Exception as e:
            field_path = f"nodes[{i}]"
            raise SchemaValidationError(file_name, field_path, str(e))
    return nodes


def validate_edges(edges_data: List[Dict], file_name: str = "workflow.yaml") -> List[Edge]:
    """Validate edge data and return list of Edge objects.

    Args:
        edges_data: List of edge dictionaries to validate.
        file_name: Name of the file being validated (for error reporting).

    Returns:
        List of validated Edge objects.

    Raises:
        SchemaValidationError: If validation fails for any edge.
    """
    edges = []
    for i, edge_dict in enumerate(edges_data):
        try:
            edge = Edge(**edge_dict)
            edges.append(edge)
        except ValidationError as e:
            field_path = f"edges[{i}]"
            raise SchemaValidationError(file_name, field_path, str(e))
        except Exception as e:
            field_path = f"edges[{i}]"
            raise SchemaValidationError(file_name, field_path, str(e))
    return edges


def validate_agents(agents_data: List[Dict], file_name: str = "agents.yaml") -> List[Dict]:
    """Validate agent data.

    Agents are validated for:
    - Required fields: id, kind, llm
    - kind must be 'agent'

    Args:
        agents_data: List of agent dictionaries to validate.
        file_name: Name of the file being validated (for error reporting).

    Returns:
        List of validated agent dictionaries.

    Raises:
        SchemaValidationError: If validation fails for any agent.
    """
    validated = []
    for i, agent in enumerate(agents_data):
        # Check required fields
        required = ["id", "kind", "llm"]
        missing = [f for f in required if f not in agent]
        if missing:
            field_path = f"agents[{i}]"
            raise SchemaValidationError(
                file_name, field_path, f"Missing required fields: {missing}"
            )
        # Validate kind is "agent"
        if agent["kind"] != "agent":
            field_path = f"agents[{i}].kind"
            raise SchemaValidationError(
                file_name, field_path, f"Expected 'agent', got '{agent['kind']}'"
            )
        validated.append(agent)
    return validated


def validate_tools(tools_data: List[Dict], file_name: str = "tools.yaml") -> List[Dict]:
    """Validate tool data.

    Tools are validated for:
    - Required fields: id, type, entrypoint, permissions
    - permissions must contain: allow_network, allow_shell, root

    Args:
        tools_data: List of tool dictionaries to validate.
        file_name: Name of the file being validated (for error reporting).

    Returns:
        List of validated tool dictionaries.

    Raises:
        SchemaValidationError: If validation fails for any tool.
    """
    validated = []
    for i, tool in enumerate(tools_data):
        # Check required fields
        required = ["id", "type", "entrypoint", "permissions"]
        missing = [f for f in required if f not in tool]
        if missing:
            field_path = f"tools[{i}]"
            raise SchemaValidationError(
                file_name, field_path, f"Missing required fields: {missing}"
            )
        # Validate permissions structure
        permissions = tool.get("permissions", {})
        perm_required = ["allow_network", "allow_shell", "root"]
        perm_missing = [f for f in perm_required if f not in permissions]
        if perm_missing:
            field_path = f"tools[{i}].permissions"
            raise SchemaValidationError(
                file_name, field_path, f"Missing permission fields: {perm_missing}"
            )
        validated.append(tool)
    return validated


def validate_memory_config(
    memory_data: Dict, file_name: str = "memory.yaml"
) -> Dict:
    """Validate memory configuration.

    Memory configuration is validated for:
    - Required stores: task_store, project_store, global_store
    - Each store must have a 'type' field
    - Optional context_profiles must be valid ContextProfile objects

    Args:
        memory_data: Memory configuration dictionary to validate.
        file_name: Name of the file being validated (for error reporting).

    Returns:
        The validated memory configuration dictionary.

    Raises:
        SchemaValidationError: If validation fails.
    """
    # Check required stores
    required_stores = ["task_store", "project_store", "global_store"]
    missing = [s for s in required_stores if s not in memory_data]
    if missing:
        raise SchemaValidationError(file_name, "memory", f"Missing stores: {missing}")

    # Validate each store has type
    for store_name in required_stores:
        if store_name not in memory_data:
            continue
        store = memory_data[store_name]
        if not isinstance(store, dict) or "type" not in store:
            raise SchemaValidationError(
                file_name, f"memory.{store_name}", "Missing 'type' field"
            )

    # Validate context profiles if present
    if "context_profiles" in memory_data:
        profiles_data = memory_data["context_profiles"]
        if not isinstance(profiles_data, list):
            raise SchemaValidationError(
                file_name, "memory.context_profiles", "Expected list"
            )
        for i, profile_dict in enumerate(profiles_data):
            try:
                ContextProfile(**profile_dict)
            except ValidationError as e:
                field_path = f"memory.context_profiles[{i}]"
                raise SchemaValidationError(file_name, field_path, str(e))
            except Exception as e:
                field_path = f"memory.context_profiles[{i}]"
                raise SchemaValidationError(file_name, field_path, str(e))

    return memory_data


def validate_exit_nodes(dag: DAG) -> None:
    """Validate exit node constraints per AGENT_ENGINE_SPEC §3.1.

    Exit node requirements:
    - Must have kind=DETERMINISTIC (cannot be AGENT)
    - Must have 0 outbound edges
    - Must have ≥1 inbound edges
    - Cannot specify tools (tools list must be empty)
    - always_fail flag only meaningful for EXIT nodes

    Args:
        dag: The DAG to validate

    Raises:
        SchemaValidationError: If exit node violates constraints
    """
    for node in dag.nodes.values():
        if node.role == NodeRole.EXIT:
            # Must be deterministic
            if node.kind != NodeKind.DETERMINISTIC:
                raise SchemaValidationError(
                    "workflow.yaml",
                    f"nodes.{node.stage_id}",
                    f"Exit node {node.stage_id}: must be DETERMINISTIC (cannot be AGENT)"
                )

            # Cannot have tools
            if node.tools:
                raise SchemaValidationError(
                    "workflow.yaml",
                    f"nodes.{node.stage_id}",
                    f"Exit node {node.stage_id}: cannot specify tools (must be read-only)"
                )

            # Must have ≥1 inbound edges
            inbound = dag.get_inbound_edges(node.stage_id)
            if not inbound:
                raise SchemaValidationError(
                    "workflow.yaml",
                    f"nodes.{node.stage_id}",
                    f"Exit node {node.stage_id}: must have at least 1 inbound edge"
                )

            # Must have 0 outbound edges
            outbound = dag.get_outbound_edges(node.stage_id)
            if outbound:
                raise SchemaValidationError(
                    "workflow.yaml",
                    f"nodes.{node.stage_id}",
                    f"Exit node {node.stage_id}: cannot have outbound edges"
                )

        else:
            # always_fail only valid for EXIT nodes
            if node.always_fail:
                raise SchemaValidationError(
                    "workflow.yaml",
                    f"nodes.{node.stage_id}",
                    f"Node {node.stage_id}: always_fail=True only valid for EXIT nodes"
                )
