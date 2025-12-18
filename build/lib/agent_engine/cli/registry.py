"""
Command registry for Phase 18 CLI Framework.

Provides decorator-based command registration and lookup.
"""

from typing import Dict, Callable, Optional, List, Tuple


class CommandRegistry:
    """
    Registry for CLI commands.

    Supports command registration, lookup, and alias resolution.
    """

    def __init__(self):
        """Initialize an empty registry."""
        self._commands: Dict[str, Callable] = {}
        self._aliases: Dict[str, str] = {}  # alias -> command name
        self._help_texts: Dict[str, str] = {}

    def register(
        self,
        name: str,
        func: Callable,
        aliases: Optional[List[str]] = None,
        help_text: Optional[str] = None,
    ) -> None:
        """
        Register a command.

        Args:
            name: Command name (without leading slash)
            func: Command function with signature (ctx: CliContext, args: str) -> None
            aliases: Optional list of aliases
            help_text: Optional help text (defaults to function docstring)
        """
        self._commands[name] = func

        # Extract help text from docstring if not provided
        if help_text is None:
            help_text = (func.__doc__ or "").strip()
        self._help_texts[name] = help_text

        # Register aliases
        if aliases:
            for alias in aliases:
                self._aliases[alias] = name

    def get_command(self, name: str) -> Optional[Callable]:
        """
        Get a command function.

        Args:
            name: Command name or alias

        Returns:
            Command function or None if not found
        """
        # Check if it's an alias
        if name in self._aliases:
            name = self._aliases[name]

        return self._commands.get(name)

    def list_commands(self) -> List[Tuple[str, str]]:
        """
        List all registered commands.

        Returns:
            List of (name, help_text) tuples
        """
        result = []
        for name in sorted(self._commands.keys()):
            help_text = self._help_texts.get(name, "")
            result.append((name, help_text))
        return result

    def get_help(self, command_name: str) -> str:
        """
        Get detailed help for a command.

        Args:
            command_name: Command name or alias

        Returns:
            Help text or "Command not found" message
        """
        # Resolve alias
        if command_name in self._aliases:
            command_name = self._aliases[command_name]

        if command_name not in self._commands:
            return f"Command '{command_name}' not found"

        help_text = self._help_texts.get(command_name, "No help available")
        return help_text

    def resolve_command_name(self, name: str) -> Optional[str]:
        """
        Resolve a command name or alias to canonical name.

        Args:
            name: Command name or alias

        Returns:
            Canonical command name or None if not found
        """
        if name in self._aliases:
            return self._aliases[name]
        if name in self._commands:
            return name
        return None


# Global registry instance
_global_registry = CommandRegistry()


def register_command(
    name: str,
    aliases: Optional[List[str]] = None,
    help_text: Optional[str] = None,
):
    """
    Decorator for registering a command.

    Args:
        name: Command name (without leading slash)
        aliases: Optional list of aliases
        help_text: Optional help text

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        _global_registry.register(name, func, aliases, help_text)
        return func

    return decorator


def get_global_registry() -> CommandRegistry:
    """
    Get the global command registry.

    Returns:
        Global CommandRegistry instance
    """
    return _global_registry
