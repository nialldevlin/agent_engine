"""
CLI context for Phase 18 CLI Framework.

Provides context object with helper methods for command execution.
"""

from typing import Dict, List, Any, Optional, Set
from datetime import datetime

from .profile import Profile
from .session import Session, SessionEntry
from .exceptions import CliError


class CliContext:
    """
    Context object for command execution.

    Provides access to session, engine, profile, and helper methods.
    """

    def __init__(
        self,
        session: Session,
        engine: Any,  # Engine type
        profile: Profile,
        workspace_root: str,
    ):
        """
        Initialize CLI context.

        Args:
            session: Session instance
            engine: Engine instance
            profile: Active profile
            workspace_root: Workspace directory path
        """
        self.session = session
        self.engine = engine
        self.active_profile = profile
        self.workspace_root = workspace_root

    @property
    def session_id(self) -> str:
        """Get current session ID."""
        return self.session.session_id

    @property
    def attached_files(self) -> Set[str]:
        """Get currently attached files."""
        return self.session.get_attached_files()

    @property
    def history(self) -> List[SessionEntry]:
        """Get session history."""
        return self.session.get_history()

    def run_engine(self, input_data: Any, start_node_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute Engine.run() and record in history.

        Args:
            input_data: Input data for engine
            start_node_id: Optional start node ID

        Returns:
            Result dictionary from engine run
        """
        try:
            # Call engine.run()
            result = self.engine.run(input_data, start_node_id=start_node_id)

            # Record in history
            entry = SessionEntry(
                session_id=self.session.session_id,
                timestamp=datetime.utcnow().isoformat(),
                role="system",
                input=input_data,
                command=None,
                engine_run_metadata=result.get("metadata", {}),
                attached_files=list(self.session.get_attached_files()),
            )
            self.session.add_entry(entry)

            return result
        except Exception as e:
            raise CliError(f"Engine execution failed: {str(e)}")

    def attach_file(self, path: str) -> None:
        """
        Attach a file to session context.

        Args:
            path: File path to attach

        Raises:
            CliError: If path is invalid or outside workspace
        """
        # Validate path is within workspace
        from .file_ops import validate_path

        validated_path = validate_path(path, self.workspace_root)
        self.session.attach_file(validated_path)

    def get_telemetry(self) -> List[Any]:
        """
        Get telemetry events from engine.

        Returns:
            List of telemetry events
        """
        if hasattr(self.engine, "telemetry"):
            if hasattr(self.engine.telemetry, "events"):
                return self.engine.telemetry.events
        return []

    def get_current_profile(self) -> Profile:
        """
        Get active profile.

        Returns:
            Active profile object
        """
        return self.active_profile

    def switch_profile(self, profile_id: str, available_profiles: List[Profile]) -> None:
        """
        Switch to a different profile.

        Args:
            profile_id: Target profile ID
            available_profiles: List of available profiles

        Raises:
            CliError: If profile not found
        """
        for profile in available_profiles:
            if profile.id == profile_id:
                self.active_profile = profile
                self.session.profile = profile
                return

        raise CliError(f"Profile '{profile_id}' not found")
