"""
Phase 18 CLI Framework - Reusable REPL for Agent Engine.

Provides a multi-turn conversational REPL with:
- Profile-based configuration
- Session history management
- Built-in command set
- Extensible command registry
- File operations with workspace safety
- Telemetry integration
"""

from .repl import REPL
from .context import CliContext
from .registry import register_command, get_global_registry
from .exceptions import CliError, CommandError
from .profile import Profile, load_profiles, get_default_profile
from .session import Session, SessionEntry

__all__ = [
    "REPL",
    "CliContext",
    "register_command",
    "get_global_registry",
    "CliError",
    "CommandError",
    "Profile",
    "load_profiles",
    "get_default_profile",
    "Session",
    "SessionEntry",
]
