"""Built-in tool definitions provided by Agent Engine.

This module documents the tools that are provided natively by the engine.
User applications can reference these by their tool_id or create custom tool definitions.

Built-in tools are registered in the schema registry and can be used by agents without
requiring custom implementation code. Tool execution is handled by the Tool Runtime.

Per AGENT_ENGINE_SPEC §4.3 and AGENT_ENGINE_OVERVIEW §8.
"""

from typing import Dict

from agent_engine.schemas import ToolCapability, ToolDefinition, ToolKind, ToolRiskLevel


# Built-in tool IDs (stable across engine versions)
BUILTIN_FILESYSTEM_WRITE = "filesystem.write_file"
BUILTIN_FILESYSTEM_READ = "filesystem.read_file"
BUILTIN_FILESYSTEM_LIST = "filesystem.list"
BUILTIN_COMMAND_RUN = "command.run"


# Built-in tool definitions
BUILTIN_TOOLS: Dict[str, ToolDefinition] = {
    BUILTIN_FILESYSTEM_WRITE: ToolDefinition(
        tool_id=BUILTIN_FILESYSTEM_WRITE,
        kind=ToolKind.DETERMINISTIC,
        name="Write File",
        description="Write content to a file within the configured workspace root.",
        inputs_schema_id="execution_input",
        outputs_schema_id="execution_output",
        capabilities=[ToolCapability.WORKSPACE_MUTATION],
        risk_level=ToolRiskLevel.MEDIUM,
        version="1.0.0",
        metadata={
            "handler": "agent_engine.runtime.tool_runtime:write_file",
            "required_args": ["path", "content"],
        },
    ),
    BUILTIN_FILESYSTEM_READ: ToolDefinition(
        tool_id=BUILTIN_FILESYSTEM_READ,
        kind=ToolKind.DETERMINISTIC,
        name="Read File",
        description="Read content from a file within the configured workspace root.",
        inputs_schema_id="execution_input",
        outputs_schema_id="execution_output",
        capabilities=[ToolCapability.DETERMINISTIC_SAFE],
        risk_level=ToolRiskLevel.LOW,
        version="1.0.0",
        metadata={
            "handler": "agent_engine.runtime.tool_runtime:read_file",
            "required_args": ["path"],
        },
    ),
    BUILTIN_FILESYSTEM_LIST: ToolDefinition(
        tool_id=BUILTIN_FILESYSTEM_LIST,
        kind=ToolKind.DETERMINISTIC,
        name="List Files",
        description="List files and directories within the configured workspace root.",
        inputs_schema_id="execution_input",
        outputs_schema_id="execution_output",
        capabilities=[ToolCapability.DETERMINISTIC_SAFE],
        risk_level=ToolRiskLevel.LOW,
        version="1.0.0",
        metadata={
            "handler": "agent_engine.runtime.tool_runtime:list_files",
            "required_args": ["path"],
        },
    ),
    BUILTIN_COMMAND_RUN: ToolDefinition(
        tool_id=BUILTIN_COMMAND_RUN,
        kind=ToolKind.DETERMINISTIC,
        name="Run Command",
        description="Execute a shell command within the configured workspace root (requires explicit permission).",
        inputs_schema_id="execution_input",
        outputs_schema_id="execution_output",
        capabilities=[ToolCapability.WORKSPACE_MUTATION, ToolCapability.EXPENSIVE],
        risk_level=ToolRiskLevel.HIGH,
        version="1.0.0",
        metadata={
            "handler": "agent_engine.runtime.tool_runtime:run_command",
            "required_args": ["command"],
            "note": "Requires explicit security permission; gated by Tool Runtime security checks.",
        },
    ),
}


def get_builtin_tool(tool_id: str) -> ToolDefinition:
    """Retrieve a built-in tool definition by ID.

    Args:
        tool_id: Built-in tool identifier (e.g., 'filesystem.write_file')

    Returns:
        ToolDefinition for the requested tool.

    Raises:
        KeyError: If tool_id is not a built-in tool.
    """
    if tool_id not in BUILTIN_TOOLS:
        raise KeyError(f"Unknown built-in tool: {tool_id}")
    return BUILTIN_TOOLS[tool_id]


def is_builtin_tool(tool_id: str) -> bool:
    """Check if a tool ID refers to a built-in tool.

    Args:
        tool_id: Tool identifier.

    Returns:
        True if this is a built-in tool; False otherwise.
    """
    return tool_id in BUILTIN_TOOLS


def list_builtin_tools() -> Dict[str, ToolDefinition]:
    """Return all built-in tool definitions.

    Returns:
        Dict mapping tool_id to ToolDefinition for all built-in tools.
    """
    return BUILTIN_TOOLS.copy()
