"""
Session management for Phase 18 CLI Framework.

Handles session state, history tracking, and optional JSONL persistence.
"""

from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Any, Set
from datetime import datetime
import json
import os
from pathlib import Path

from .profile import Profile
from .exceptions import CliError
from agent_engine.paths import resolve_state_root, ensure_directory


@dataclass
class SessionEntry:
    """A single session history entry."""

    session_id: str
    timestamp: str  # ISO-8601 format
    role: str  # "user" or "system"
    input: Any
    command: Optional[str] = None
    engine_run_metadata: Optional[Dict[str, Any]] = None
    attached_files: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionEntry":
        """Create from dictionary."""
        return cls(
            session_id=data["session_id"],
            timestamp=data["timestamp"],
            role=data["role"],
            input=data["input"],
            command=data.get("command"),
            engine_run_metadata=data.get("engine_run_metadata"),
            attached_files=data.get("attached_files", []),
        )


class Session:
    """
    Session state management.

    Tracks history, attached files, and optional disk persistence.
    """

    def __init__(self, session_id: str, profile: Profile, state_root: Optional[Path] = None):
        """
        Initialize a session.

        Args:
            session_id: Unique session identifier
            profile: Active profile configuration
        """
        self.session_id = session_id
        self.profile = profile
        self._history: List[SessionEntry] = []
        self._attached_files: Set[str] = set()
        self._last_user_input: Optional[str] = None
        root = Path(state_root).resolve() if state_root else resolve_state_root(profile.default_config_dir)
        self._state_root = ensure_directory(root)

    def add_entry(self, entry: SessionEntry) -> None:
        """
        Add entry to history.

        Args:
            entry: SessionEntry to add
        """
        # Enforce max_history_items limit
        max_items = self.profile.session_policies.max_history_items
        if len(self._history) >= max_items:
            self._history.pop(0)

        self._history.append(entry)

        # Track last user input
        if entry.role == "user":
            self._last_user_input = entry.input

    def get_history(self) -> List[SessionEntry]:
        """
        Get session history.

        Returns:
            List of SessionEntry objects
        """
        return self._history.copy()

    def get_last_user_prompt(self) -> Optional[str]:
        """
        Get the last user input.

        Returns:
            Last user input or None if no user input in history
        """
        return self._last_user_input

    def attach_file(self, path: str) -> None:
        """
        Attach a file to the session.

        Args:
            path: File path to attach
        """
        self._attached_files.add(path)

    def get_attached_files(self) -> Set[str]:
        """
        Get attached files.

        Returns:
            Set of attached file paths
        """
        return self._attached_files.copy()

    def persist(self) -> None:
        """
        Persist session to disk (JSONL format) if enabled.

        Creates parent directories if needed.

        Raises:
            CliError: If persistence fails
        """
        if not self.profile.session_policies.persist_history:
            return

        history_file = self.profile.session_policies.history_file
        if not history_file:
            history_file = str(self._state_root / "sessions" / "history.jsonl")

        try:
            # Create parent directories
            parent_dir = os.path.dirname(history_file)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)

            # Append entries to JSONL file
            with open(history_file, "a") as f:
                for entry in self._history:
                    f.write(json.dumps(entry.to_dict()) + "\n")
        except IOError as e:
            raise CliError(f"Failed to persist session: {str(e)}")

    def load(self) -> None:
        """
        Load session from disk if exists.

        Raises:
            CliError: If loading fails
        """
        if not self.profile.session_policies.persist_history:
            return

        history_file = self.profile.session_policies.history_file
        if not history_file:
            history_file = str(self._state_root / "sessions" / "history.jsonl")

        if not os.path.exists(history_file):
            return

        try:
            with open(history_file, "r") as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        entry = SessionEntry.from_dict(data)
                        # Skip enforcing max items during load
                        self._history.append(entry)
                        if entry.role == "user":
                            self._last_user_input = entry.input

            # Enforce max items after loading
            max_items = self.profile.session_policies.max_history_items
            if len(self._history) > max_items:
                self._history = self._history[-max_items:]
        except (IOError, json.JSONDecodeError) as e:
            raise CliError(f"Failed to load session: {str(e)}")

    def clear_completed_tasks(self) -> None:
        """Optional cleanup for completed tasks."""
        pass
