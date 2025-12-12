"""
Main REPL loop for Phase 18 CLI Framework.

Implements the interactive REPL for multi-turn conversational sessions.
"""

import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime
import importlib

from .profile import Profile, load_profiles, get_default_profile
from .session import Session, SessionEntry
from .context import CliContext
from .registry import get_global_registry
from .exceptions import CliError, CommandError
from . import commands  # Import to register built-in commands
from agent_engine.paths import resolve_state_root, ensure_directory


class REPL:
    """
    Interactive REPL for multi-turn conversations.

    Manages profiles, sessions, and command execution.
    """

    def __init__(
        self,
        engine: Any,  # Engine instance
        config_dir: str,
        profile_id: Optional[str] = None,
    ):
        """
        Initialize REPL.

        Args:
            engine: Engine instance
            config_dir: Directory containing cli_profiles.yaml
            profile_id: Optional profile ID to activate (defaults to first profile)
        """
        self.engine = engine
        self.config_dir = config_dir

        # Load profiles
        try:
            self.profiles = load_profiles(config_dir)
        except CliError:
            self.profiles = [get_default_profile()]

        # Select initial profile
        self.active_profile = self._get_profile(profile_id)

        # Initialize session
        session_root = ensure_directory(resolve_state_root(self.active_profile.default_config_dir or config_dir))
        self.session = Session(str(uuid.uuid4()), self.active_profile, state_root=session_root)
        try:
            self.session.load()
        except CliError as e:
            print(f"Warning: Could not load session history: {e}")

        # Initialize context
        self.context = CliContext(
            session=self.session,
            engine=engine,
            profile=self.active_profile,
            workspace_root=self.active_profile.default_config_dir or config_dir,
        )

        # Load custom commands
        self._load_custom_commands(self.active_profile)

    def _get_profile(self, profile_id: Optional[str]) -> Profile:
        """
        Get profile by ID or return first profile.

        Args:
            profile_id: Optional profile ID

        Returns:
            Profile object

        Raises:
            CliError: If specified profile not found
        """
        if profile_id:
            for profile in self.profiles:
                if profile.id == profile_id:
                    return profile
            raise CliError(f"Profile '{profile_id}' not found")

        # Return first or default
        return self.profiles[0] if self.profiles else get_default_profile()

    def _load_custom_commands(self, profile: Profile) -> None:
        """
        Load custom commands from profile.

        Args:
            profile: Profile containing custom command definitions
        """
        registry = get_global_registry()

        for custom_cmd in profile.custom_commands:
            try:
                # Parse entrypoint: "module.path:function_name"
                if ":" not in custom_cmd.entrypoint:
                    print(
                        f"Warning: Invalid entrypoint format: {custom_cmd.entrypoint}"
                    )
                    continue

                module_path, func_name = custom_cmd.entrypoint.rsplit(":", 1)

                # Dynamically import
                module = importlib.import_module(module_path)
                func = getattr(module, func_name, None)

                if func is None:
                    print(f"Warning: Function not found: {custom_cmd.entrypoint}")
                    continue

                # Register command
                registry.register(
                    custom_cmd.name,
                    func,
                    aliases=custom_cmd.aliases,
                    help_text=custom_cmd.help,
                )

            except Exception as e:
                print(f"Warning: Failed to load custom command '{custom_cmd.name}': {e}")

    def run(self) -> None:
        """
        Main REPL loop.

        Displays prompt, reads input, executes commands or engine runs,
        and loops until /quit.
        """
        print(f"Agent Engine REPL (profile: {self.active_profile.id})")
        print("Type /help for available commands or /quit to exit")
        print()

        try:
            while True:
                try:
                    # Display prompt
                    prompt = f"[{self.active_profile.id}]> "
                    user_input = input(prompt)

                    if not user_input.strip():
                        continue

                    # Record user input in history
                    history_entry = SessionEntry(
                        session_id=self.session.session_id,
                        timestamp=datetime.utcnow().isoformat(),
                        role="user",
                        input=user_input,
                        attached_files=list(self.session.get_attached_files()),
                    )
                    self.session.add_entry(history_entry)

                    # Parse and execute
                    if user_input.startswith("/"):
                        # Command
                        self._execute_command(user_input)
                    else:
                        # Engine input
                        self._execute_engine_input(user_input)

                    # Persist session after each turn if enabled
                    if self.active_profile.session_policies.persist_history:
                        try:
                            self.session.persist()
                        except CliError as e:
                            print(f"Warning: Could not persist session: {e}")

                except KeyboardInterrupt:
                    print("\nInterrupted")
                    continue
                except CommandError as e:
                    print(f"Error: {e}")
                    continue
                except CliError as e:
                    print(f"Error: {e}")
                    continue

        except EOFError:
            print()
            print("EOF - exiting")

    def _execute_command(self, input_str: str) -> None:
        """
        Execute a command.

        Args:
            input_str: Raw command input (e.g., "/help" or "/open file.txt")
        """
        parts = input_str.lstrip("/").split(None, 1)
        command_name = parts[0]
        args = parts[1] if len(parts) > 1 else ""

        # Get registry
        registry = get_global_registry()
        command_func = registry.get_command(command_name)

        if command_func is None:
            raise CommandError(
                message=f"Unknown command: /{command_name}",
                command_name=command_name,
            )

        # Handle mode command specially to allow profile switching
        if command_name == "mode" and args:
            # Try to switch profile
            try:
                self.context.switch_profile(args.strip(), self.profiles)
                self.active_profile = self.context.active_profile
                print(f"Switched to profile: {self.active_profile.id}")
            except CliError as e:
                raise CommandError(
                    message=str(e),
                    command_name="mode",
                    args=args,
                )
            return

        # Execute command
        try:
            command_func(self.context, args)
        except SystemExit:
            raise
        except CommandError:
            raise
        except Exception as e:
            raise CommandError(
                message=str(e),
                command_name=command_name,
                args=args,
            )

    def _execute_engine_input(self, user_input: str) -> None:
        """
        Execute engine input.

        Args:
            user_input: User input to send to engine
        """
        # Apply input mappings from profile
        input_mapping = self.active_profile.input_mappings.default

        # Build payload
        payload = user_input

        # Add context if configured
        if input_mapping.include_profile_id:
            payload = {
                "input": user_input,
                "profile_id": self.active_profile.id,
            }

        if input_mapping.include_session_id:
            if isinstance(payload, dict):
                payload["session_id"] = self.session.session_id
            else:
                payload = {
                    "input": user_input,
                    "session_id": self.session.session_id,
                }

        # Add attached files if configured
        if input_mapping.attach_files_as_context:
            attached = list(self.session.get_attached_files())
            if isinstance(payload, dict):
                payload["attached_files"] = attached
            else:
                payload = {
                    "input": user_input,
                    "attached_files": attached,
                }

        # Run engine
        try:
            result = self.context.run_engine(payload)

            # Display result in human-friendly format
            self._display_result(result)

            # Display telemetry if enabled
            if self.active_profile.telemetry_overlays.enabled:
                self._display_telemetry(
                    self.context.get_telemetry(),
                    self.active_profile.telemetry_overlays.level,
                )

        except CliError as e:
            raise
        except Exception as e:
            raise CliError(f"Engine execution failed: {str(e)}")

    def _display_result(self, result: Dict[str, Any]) -> None:
        """
        Display engine result in human-friendly format.

        Args:
            result: Result dict from engine.run()
        """
        import json

        # Extract key fields
        task_id = result.get("task_id", "unknown")
        status = result.get("status", "unknown")
        execution_time_ms = result.get("execution_time_ms", 0)
        output = result.get("output")
        node_sequence = result.get("node_sequence", [])
        history = result.get("history", [])

        # Status indicator
        status_icon = "✓" if status == "success" else "⚠" if status == "partial" else "✗"

        print()
        print(f"{status_icon} Status: {status.upper()}")
        print(f"  Task ID: {task_id}")
        print(f"  Time: {execution_time_ms}ms")

        # Show node sequence
        if node_sequence:
            print(f"  Nodes: {' → '.join(node_sequence)}")

        # Display output
        if output is not None:
            print()
            print("Output:")
            print("-" * 60)

            # Extract and display content from common structures
            content = None
            if isinstance(output, dict):
                # Try common content field names
                for field in ["content", "text", "message", "result", "data"]:
                    if field in output:
                        content = output[field]
                        break

            # Display extracted content or fall back to original output
            if content is not None:
                print(str(content))
            elif isinstance(output, str):
                print(output)
            elif isinstance(output, (dict, list)):
                # Fall back to JSON if no content field found
                try:
                    formatted = json.dumps(output, indent=2)
                    print(formatted)
                except (TypeError, ValueError):
                    print(str(output))
            else:
                # Other types
                print(str(output))

            print("-" * 60)

        # Show brief execution history
        if history:
            print()
            print("Execution History:")
            for i, record in enumerate(history, 1):
                node_id = record.get("node_id", "unknown")
                node_status = record.get("node_status", "unknown")
                node_role = record.get("node_role", "")

                # Format node status with icon
                if node_status == "completed":
                    node_icon = "✓"
                elif node_status == "failed":
                    node_icon = "✗"
                else:
                    node_icon = "•"

                role_label = f" ({node_role})" if node_role else ""
                print(f"  {i}. {node_icon} {node_id}{role_label}")

    def _display_telemetry(self, events: List[Any], level: str) -> None:
        """
        Display telemetry events.

        Args:
            events: List of telemetry events
            level: Display level ("summary" or "verbose")
        """
        if not events:
            return

        print()
        print("=== Telemetry ===")

        if level == "summary":
            # Show only task/error events
            for event in events:
                # Handle both Event objects and dictionaries
                if isinstance(event, dict):
                    event_type = event.get("event_type", "unknown")
                else:
                    event_type = getattr(event, "event_type", "unknown")

                if event_type in ["task_start", "task_end", "error"]:
                    print(f"[{event_type}] {event}")
        else:
            # Show all events
            for event in events:
                print(f"[{event}]")
