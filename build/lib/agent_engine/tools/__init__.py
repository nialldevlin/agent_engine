"""Built-in and custom tools for the Agent Engine.

This package contains built-in tool definitions and tool runtime support.
Built-in tools (filesystem operations, command execution) are provided by the engine
and can be referenced by agents via manifest-defined tool invocations.
"""

from .builtin import (
    BUILTIN_COMMAND_RUN,
    BUILTIN_FILESYSTEM_LIST,
    BUILTIN_FILESYSTEM_READ,
    BUILTIN_FILESYSTEM_WRITE,
    BUILTIN_TOOLS,
    get_builtin_tool,
    is_builtin_tool,
    list_builtin_tools,
)

__all__ = [
    "BUILTIN_COMMAND_RUN",
    "BUILTIN_FILESYSTEM_LIST",
    "BUILTIN_FILESYSTEM_READ",
    "BUILTIN_FILESYSTEM_WRITE",
    "BUILTIN_TOOLS",
    "get_builtin_tool",
    "is_builtin_tool",
    "list_builtin_tools",
]
