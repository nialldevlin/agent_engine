"""
CLI exception hierarchy for Phase 18 CLI Framework.

Provides structured exceptions for CLI error handling with JSON serialization support.
"""

from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class CliError(Exception):
    """Base exception for CLI errors."""

    message: str

    def __str__(self) -> str:
        """Return human-readable error message."""
        return self.message

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class CommandError(CliError):
    """Exception for command execution errors."""

    command_name: str = ""
    args: Optional[str] = None

    def __str__(self) -> str:
        """Return human-readable error message with command context."""
        msg = f"Command '{self.command_name}' error: {self.message}"
        if self.args:
            msg += f" (args: {self.args})"
        return msg
