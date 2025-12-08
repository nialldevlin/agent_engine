"""Tests for built-in tool catalog."""

import pytest

from agent_engine.tools import (
    BUILTIN_COMMAND_RUN,
    BUILTIN_FILESYSTEM_LIST,
    BUILTIN_FILESYSTEM_READ,
    BUILTIN_FILESYSTEM_WRITE,
    BUILTIN_TOOLS,
    get_builtin_tool,
    is_builtin_tool,
    list_builtin_tools,
)
from agent_engine.schemas import ToolCapability, ToolKind, ToolRiskLevel


def test_builtin_tools_registered() -> None:
    """Test that all built-in tools are registered."""
    assert BUILTIN_FILESYSTEM_WRITE in BUILTIN_TOOLS
    assert BUILTIN_FILESYSTEM_READ in BUILTIN_TOOLS
    assert BUILTIN_FILESYSTEM_LIST in BUILTIN_TOOLS
    assert BUILTIN_COMMAND_RUN in BUILTIN_TOOLS


def test_get_builtin_tool_write() -> None:
    """Test retrieving filesystem.write_file tool."""
    tool = get_builtin_tool(BUILTIN_FILESYSTEM_WRITE)
    assert tool.tool_id == BUILTIN_FILESYSTEM_WRITE
    assert tool.kind == ToolKind.DETERMINISTIC
    assert ToolCapability.WORKSPACE_MUTATION in tool.capabilities
    assert tool.risk_level == ToolRiskLevel.MEDIUM


def test_get_builtin_tool_read() -> None:
    """Test retrieving filesystem.read_file tool."""
    tool = get_builtin_tool(BUILTIN_FILESYSTEM_READ)
    assert tool.tool_id == BUILTIN_FILESYSTEM_READ
    assert tool.kind == ToolKind.DETERMINISTIC
    assert ToolCapability.DETERMINISTIC_SAFE in tool.capabilities
    assert tool.risk_level == ToolRiskLevel.LOW


def test_get_builtin_tool_list() -> None:
    """Test retrieving filesystem.list tool."""
    tool = get_builtin_tool(BUILTIN_FILESYSTEM_LIST)
    assert tool.tool_id == BUILTIN_FILESYSTEM_LIST
    assert tool.kind == ToolKind.DETERMINISTIC
    assert ToolCapability.DETERMINISTIC_SAFE in tool.capabilities
    assert tool.risk_level == ToolRiskLevel.LOW


def test_get_builtin_tool_run_command() -> None:
    """Test retrieving command.run tool."""
    tool = get_builtin_tool(BUILTIN_COMMAND_RUN)
    assert tool.tool_id == BUILTIN_COMMAND_RUN
    assert tool.kind == ToolKind.DETERMINISTIC
    assert ToolCapability.WORKSPACE_MUTATION in tool.capabilities
    assert tool.risk_level == ToolRiskLevel.HIGH


def test_get_builtin_tool_unknown() -> None:
    """Test that unknown tool ID raises KeyError."""
    with pytest.raises(KeyError):
        get_builtin_tool("unknown.tool")


def test_is_builtin_tool() -> None:
    """Test is_builtin_tool function."""
    assert is_builtin_tool(BUILTIN_FILESYSTEM_WRITE)
    assert is_builtin_tool(BUILTIN_FILESYSTEM_READ)
    assert is_builtin_tool(BUILTIN_FILESYSTEM_LIST)
    assert is_builtin_tool(BUILTIN_COMMAND_RUN)
    assert not is_builtin_tool("unknown.tool")
    assert not is_builtin_tool("custom_tool")


def test_list_builtin_tools() -> None:
    """Test listing all built-in tools."""
    tools = list_builtin_tools()
    assert len(tools) == 4
    assert all(isinstance(v.tool_id, str) for v in tools.values())
    # Verify it returns a copy, not the original dict
    tools["custom"] = None
    assert "custom" not in BUILTIN_TOOLS
