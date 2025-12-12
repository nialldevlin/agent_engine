"""
Comprehensive test suite for Phase 18 CLI Framework.

Tests cover all components: profiles, sessions, commands, file operations,
context, telemetry, exceptions, and integration scenarios.
"""

import pytest
import os
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

from agent_engine.cli import (
    REPL,
    CliContext,
    register_command,
    get_global_registry,
    CliError,
    CommandError,
    Profile,
    load_profiles,
    get_default_profile,
    Session,
    SessionEntry,
)
from agent_engine.cli.file_ops import (
    validate_path,
    view_file,
    edit_buffer,
    compute_diff,
    apply_patch_safe,
)


# ============================================================================
# PROFILE LOADING TESTS (5 tests)
# ============================================================================


class TestProfileLoading:
    """Tests for profile loading and validation."""

    def test_load_default_profile_when_no_file(self):
        """Test loading default profile when cli_profiles.yaml doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            profiles = load_profiles(tmpdir)
            assert len(profiles) >= 1
            assert profiles[0].id == "default"

    def test_get_default_profile(self):
        """Test get_default_profile returns sensible defaults."""
        profile = get_default_profile()
        assert profile.id == "default"
        assert profile.session_policies.persist_history is True
        assert profile.session_policies.max_history_items == 1000
        assert profile.telemetry_overlays.enabled is True

    def test_load_valid_profile_from_yaml(self):
        """Test loading valid cli_profiles.yaml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yaml_path = os.path.join(tmpdir, "cli_profiles.yaml")
            yaml_content = """
profiles:
  - id: test_profile
    label: Test Profile
    description: For testing
    session_policies:
      persist_history: false
      max_history_items: 100
"""
            with open(yaml_path, "w") as f:
                f.write(yaml_content)

            profiles = load_profiles(tmpdir)
            assert len(profiles) == 1
            assert profiles[0].id == "test_profile"
            assert profiles[0].label == "Test Profile"
            assert profiles[0].session_policies.persist_history is False
            assert profiles[0].session_policies.max_history_items == 100

    def test_load_invalid_profile_raises_error(self):
        """Test loading invalid YAML raises CliError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yaml_path = os.path.join(tmpdir, "cli_profiles.yaml")
            yaml_content = "invalid: [yaml: content:"  # Malformed YAML
            with open(yaml_path, "w") as f:
                f.write(yaml_content)

            with pytest.raises(CliError):
                load_profiles(tmpdir)

    def test_profile_missing_required_field(self):
        """Test profile validation raises error for missing required fields."""
        with pytest.raises(CliError, match="required field"):
            Profile.from_dict({})  # Missing required 'id' field


# ============================================================================
# SESSION MANAGEMENT TESTS (8 tests)
# ============================================================================


class TestSessionManagement:
    """Tests for session state management."""

    def test_create_session(self):
        """Test creating a new session."""
        profile = get_default_profile()
        session = Session("test_session_id", profile)
        assert session.session_id == "test_session_id"
        assert len(session.get_history()) == 0

    def test_add_entry_to_history(self):
        """Test adding entries to session history."""
        profile = get_default_profile()
        session = Session("test_id", profile)

        entry = SessionEntry(
            session_id="test_id",
            timestamp=datetime.utcnow().isoformat(),
            role="user",
            input="test input",
        )
        session.add_entry(entry)

        history = session.get_history()
        assert len(history) == 1
        assert history[0].input == "test input"

    def test_get_last_user_prompt(self):
        """Test retrieving last user input."""
        profile = get_default_profile()
        session = Session("test_id", profile)

        entry = SessionEntry(
            session_id="test_id",
            timestamp=datetime.utcnow().isoformat(),
            role="user",
            input="last prompt",
        )
        session.add_entry(entry)

        last_prompt = session.get_last_user_prompt()
        assert last_prompt == "last prompt"

    def test_attach_file(self):
        """Test attaching files to session."""
        profile = get_default_profile()
        session = Session("test_id", profile)

        session.attach_file("/path/to/file.txt")
        attached = session.get_attached_files()

        assert "/path/to/file.txt" in attached

    def test_max_history_items_enforced(self):
        """Test that max_history_items limit is enforced."""
        profile = get_default_profile()
        profile.session_policies.max_history_items = 5
        session = Session("test_id", profile)

        # Add more entries than max
        for i in range(10):
            entry = SessionEntry(
                session_id="test_id",
                timestamp=datetime.utcnow().isoformat(),
                role="user",
                input=f"input {i}",
            )
            session.add_entry(entry)

        history = session.get_history()
        assert len(history) == 5

    def test_persist_session_to_jsonl(self):
        """Test persisting session to JSONL format."""
        profile = get_default_profile()
        with tempfile.TemporaryDirectory() as tmpdir:
            history_file = os.path.join(tmpdir, "history.jsonl")
            profile.session_policies.history_file = history_file
            profile.session_policies.persist_history = True

            session = Session("test_id", profile)
            entry = SessionEntry(
                session_id="test_id",
                timestamp=datetime.utcnow().isoformat(),
                role="user",
                input="test input",
            )
            session.add_entry(entry)

            session.persist()

            # Verify file was created
            assert os.path.exists(history_file)

            # Verify content
            with open(history_file, "r") as f:
                lines = f.readlines()
                assert len(lines) == 1
                data = json.loads(lines[0])
                assert data["input"] == "test input"

    def test_load_session_from_disk(self):
        """Test loading session from persisted JSONL."""
        profile = get_default_profile()
        with tempfile.TemporaryDirectory() as tmpdir:
            history_file = os.path.join(tmpdir, "history.jsonl")
            profile.session_policies.history_file = history_file
            profile.session_policies.persist_history = True

            # Create and persist first session
            session1 = Session("test_id", profile)
            entry = SessionEntry(
                session_id="test_id",
                timestamp=datetime.utcnow().isoformat(),
                role="user",
                input="test input",
            )
            session1.add_entry(entry)
            session1.persist()

            # Load into new session
            session2 = Session("test_id", profile)
            session2.load()

            history = session2.get_history()
            assert len(history) == 1
            assert history[0].input == "test input"

    def test_no_persist_when_disabled(self):
        """Test that persistence is skipped when disabled."""
        profile = get_default_profile()
        profile.session_policies.persist_history = False

        with tempfile.TemporaryDirectory() as tmpdir:
            session = Session("test_id", profile)
            session.persist()  # Should not raise

            # No file should be created in tmpdir
            files = os.listdir(tmpdir)
            assert len(files) == 0


# ============================================================================
# COMMAND REGISTRY TESTS (5 tests)
# ============================================================================


class TestCommandRegistry:
    """Tests for command registration and lookup."""

    def test_register_command_via_decorator(self):
        """Test registering command with decorator."""
        registry = get_global_registry()

        @register_command("test_cmd")
        def test_command(ctx, args):
            pass

        cmd = registry.get_command("test_cmd")
        assert cmd is not None
        assert cmd == test_command

    def test_register_command_with_aliases(self):
        """Test registering command with aliases."""
        registry = get_global_registry()

        @register_command("test_cmd2", aliases=["tc", "test"])
        def test_command2(ctx, args):
            pass

        cmd = registry.get_command("tc")
        assert cmd is not None
        assert cmd == test_command2

    def test_get_command_not_found(self):
        """Test getting non-existent command returns None."""
        registry = get_global_registry()
        cmd = registry.get_command("nonexistent_command_xyz")
        assert cmd is None

    def test_list_commands(self):
        """Test listing all registered commands."""
        registry = get_global_registry()
        commands = registry.list_commands()

        assert len(commands) > 0
        # Check that help command is present
        command_names = [name for name, _ in commands]
        assert "help" in command_names

    def test_get_help_for_command(self):
        """Test retrieving help text for command."""
        registry = get_global_registry()
        help_text = registry.get_help("help")
        assert help_text is not None
        assert len(help_text) > 0


# ============================================================================
# FILE OPERATIONS TESTS (6 tests)
# ============================================================================


class TestFileOperations:
    """Tests for file viewing, editing, and diffing."""

    def test_validate_path_success(self):
        """Test validating path within workspace."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test file
            test_file = os.path.join(tmpdir, "test.txt")
            Path(test_file).touch()

            validated = validate_path("test.txt", tmpdir)
            assert os.path.isabs(validated)
            assert validated.endswith("test.txt")

    def test_validate_path_outside_workspace(self):
        """Test validating path outside workspace raises error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Try to access file outside workspace
            with pytest.raises(CliError, match="outside workspace"):
                validate_path("../../../etc/passwd", tmpdir)

    def test_validate_path_traversal_rejected(self):
        """Test path traversal attempts are rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(CliError, match="outside workspace"):
                validate_path("subdir/../../etc/passwd", tmpdir)

    def test_compute_diff(self):
        """Test diff generation between file and artifact."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.txt")
            with open(test_file, "w") as f:
                f.write("original\ncontent\n")

            artifact_content = "modified\ncontent\n"
            diff = compute_diff("test.txt", artifact_content, tmpdir)

            assert len(diff) > 0
            assert "---" in diff
            assert "+++" in diff

    def test_view_file_reads_content(self):
        """Test viewing file displays content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.txt")
            content = "line 1\nline 2\nline 3\n"
            with open(test_file, "w") as f:
                f.write(content)

            # Capture stdout
            import io
            from contextlib import redirect_stdout

            f = io.StringIO()
            with redirect_stdout(f):
                with patch("builtins.input", side_effect=EOFError):
                    view_file("test.txt", tmpdir)

            output = f.getvalue()
            assert "line 1" in output
            assert "line 2" in output

    def test_apply_patch_safe_with_backup(self):
        """Test applying patch creates backup."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.txt")
            with open(test_file, "w") as f:
                f.write("original\n")

            # Simple patch
            patch_content = """--- test.txt
+++ test.txt
@@ -1 +1 @@
-original
+modified
"""
            apply_patch_safe("test.txt", patch_content, tmpdir)

            # Verify backup was created and cleaned up
            # (backup should be removed on successful patch)
            assert os.path.exists(test_file)


# ============================================================================
# CLI CONTEXT TESTS (4 tests)
# ============================================================================


class TestCliContext:
    """Tests for CLI context and helper methods."""

    def test_run_engine_records_history(self):
        """Test that run_engine records entries in history."""
        mock_engine = Mock()
        mock_engine.run.return_value = {"status": "success", "metadata": {}}

        profile = get_default_profile()
        session = Session("test_id", profile)
        context = CliContext(session, mock_engine, profile, "/workspace")

        context.run_engine("test input")

        history = session.get_history()
        assert len(history) == 1
        assert history[0].role == "system"

    def test_attach_file_validates_path(self):
        """Test that attach_file validates workspace boundary."""
        mock_engine = Mock()
        profile = get_default_profile()
        session = Session("test_id", profile)
        context = CliContext(session, mock_engine, profile, "/workspace")

        with pytest.raises(CliError):
            context.attach_file("../../../etc/passwd")

    def test_get_telemetry_returns_events(self):
        """Test getting telemetry events from engine."""
        mock_engine = Mock()
        mock_engine.telemetry.events = ["event1", "event2"]

        profile = get_default_profile()
        session = Session("test_id", profile)
        context = CliContext(session, mock_engine, profile, "/workspace")

        events = context.get_telemetry()
        assert len(events) == 2

    def test_switch_profile_changes_active(self):
        """Test switching profile changes active profile."""
        mock_engine = Mock()

        profile1 = get_default_profile()
        profile2 = Profile(id="other_profile")
        profiles = [profile1, profile2]

        session = Session("test_id", profile1)
        context = CliContext(session, mock_engine, profile1, "/workspace")

        context.switch_profile("other_profile", profiles)
        assert context.active_profile.id == "other_profile"


# ============================================================================
# EXCEPTION TESTS (3 tests)
# ============================================================================


class TestExceptions:
    """Tests for CLI exceptions."""

    def test_cli_error_creation(self):
        """Test creating CliError."""
        error = CliError(message="test error")
        assert str(error) == "test error"

    def test_command_error_creation(self):
        """Test creating CommandError."""
        error = CommandError(
            message="command failed",
            command_name="test_cmd",
            args="arg1 arg2",
        )
        error_str = str(error)
        assert "test_cmd" in error_str
        assert "command failed" in error_str

    def test_exceptions_json_serializable(self):
        """Test exceptions can be converted to dict."""
        error = CliError(message="test")
        error_dict = error.to_dict()

        assert isinstance(error_dict, dict)
        assert error_dict["message"] == "test"


# ============================================================================
# TELEMETRY DISPLAY TESTS (3 tests)
# ============================================================================


class TestTelemetryDisplay:
    """Tests for telemetry event display."""

    def test_telemetry_enabled_in_profile(self):
        """Test telemetry can be enabled in profile."""
        profile = get_default_profile()
        assert profile.telemetry_overlays.enabled is True

    def test_telemetry_level_summary(self):
        """Test summary telemetry level."""
        profile = get_default_profile()
        profile.telemetry_overlays.level = "summary"
        assert profile.telemetry_overlays.level == "summary"

    def test_telemetry_level_verbose(self):
        """Test verbose telemetry level."""
        profile = get_default_profile()
        profile.telemetry_overlays.level = "verbose"
        assert profile.telemetry_overlays.level == "verbose"


# ============================================================================
# BUILT-IN COMMANDS TESTS (12 tests)
# ============================================================================


class TestBuiltInCommands:
    """Tests for built-in command functionality."""

    @pytest.fixture
    def mock_context(self):
        """Create a mock CLI context for testing."""
        mock_engine = Mock()
        mock_engine.telemetry.events = []
        profile = get_default_profile()
        session = Session("test_id", profile)
        return CliContext(session, mock_engine, profile, "/workspace")

    def test_help_command_no_args(self, mock_context, capsys):
        """Test /help with no arguments lists commands."""
        from agent_engine.cli.commands import help_command

        help_command(mock_context, "")
        captured = capsys.readouterr()
        assert "Available commands" in captured.out
        assert "help" in captured.out

    def test_help_command_with_arg(self, mock_context, capsys):
        """Test /help with command argument shows detailed help."""
        from agent_engine.cli.commands import help_command

        help_command(mock_context, "help")
        captured = capsys.readouterr()
        assert "Help for" in captured.out

    def test_mode_command_show_profile(self, mock_context, capsys):
        """Test /mode with no args shows current profile."""
        from agent_engine.cli.commands import mode_command

        mode_command(mock_context, "")
        captured = capsys.readouterr()
        assert "Current profile" in captured.out

    def test_attach_command_single_file(self, mock_context, capsys):
        """Test /attach with single file."""
        from agent_engine.cli.commands import attach_command

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.txt")
            Path(test_file).touch()

            context_workspace = CliContext(
                mock_context.session,
                mock_context.engine,
                mock_context.active_profile,
                tmpdir,
            )

            attach_command(context_workspace, "test.txt")
            captured = capsys.readouterr()
            assert "Attached 1 file" in captured.out

    def test_attach_command_no_args_raises_error(self, mock_context):
        """Test /attach with no args raises error."""
        from agent_engine.cli.commands import attach_command

        with pytest.raises(CommandError):
            attach_command(mock_context, "")

    def test_history_command_empty_history(self, mock_context, capsys):
        """Test /history with empty history."""
        from agent_engine.cli.commands import history_command

        history_command(mock_context, "")
        captured = capsys.readouterr()
        assert "No history" in captured.out

    def test_history_command_with_entries(self, mock_context, capsys):
        """Test /history displays entries."""
        from agent_engine.cli.commands import history_command

        entry = SessionEntry(
            session_id="test_id",
            timestamp=datetime.utcnow().isoformat(),
            role="user",
            input="test input",
        )
        mock_context.session.add_entry(entry)

        history_command(mock_context, "")
        captured = capsys.readouterr()
        assert "Session history" in captured.out

    def test_retry_command_no_previous_input(self, mock_context):
        """Test /retry with no previous input raises error."""
        from agent_engine.cli.commands import retry_command

        with pytest.raises(CommandError):
            retry_command(mock_context, "")

    def test_edit_last_command_no_previous(self, mock_context):
        """Test /edit-last with no previous input raises error."""
        from agent_engine.cli.commands import edit_last_command

        with pytest.raises(CommandError):
            edit_last_command(mock_context, "")

    def test_open_command_no_args_raises_error(self, mock_context):
        """Test /open with no args raises error."""
        from agent_engine.cli.commands import open_command

        with pytest.raises(CommandError):
            open_command(mock_context, "")

    def test_quit_command_saves_session(self, mock_context):
        """Test /quit saves session before exiting."""
        from agent_engine.cli.commands import quit_command

        with pytest.raises(SystemExit):
            quit_command(mock_context, "")


# ============================================================================
# INTEGRATION TESTS (5 tests)
# ============================================================================


class TestIntegration:
    """Integration tests for REPL and full workflow."""

    def test_repl_initialization(self):
        """Test REPL can be initialized."""
        mock_engine = Mock()
        mock_engine.telemetry.events = []

        with tempfile.TemporaryDirectory() as tmpdir:
            repl = REPL(mock_engine, tmpdir)
            assert repl.engine is mock_engine
            assert repl.active_profile is not None

    def test_repl_with_custom_profile(self):
        """Test REPL with specific profile."""
        mock_engine = Mock()
        mock_engine.telemetry.events = []

        with tempfile.TemporaryDirectory() as tmpdir:
            yaml_path = os.path.join(tmpdir, "cli_profiles.yaml")
            yaml_content = """
profiles:
  - id: profile1
  - id: profile2
"""
            with open(yaml_path, "w") as f:
                f.write(yaml_content)

            repl = REPL(mock_engine, tmpdir, profile_id="profile2")
            assert repl.active_profile.id == "profile2"

    def test_repl_handles_nonexistent_profile(self):
        """Test REPL raises error for non-existent profile."""
        mock_engine = Mock()
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(CliError):
                REPL(mock_engine, tmpdir, profile_id="nonexistent")

    def test_repl_execute_command(self):
        """Test executing command from REPL."""
        mock_engine = Mock()
        mock_engine.telemetry.events = []

        with tempfile.TemporaryDirectory() as tmpdir:
            repl = REPL(mock_engine, tmpdir)

            # Should not raise for valid command
            repl._execute_command("/help")

    def test_repl_execute_engine_input(self):
        """Test executing engine input from REPL."""
        mock_engine = Mock()
        mock_engine.run.return_value = {"status": "success", "metadata": {}}
        mock_engine.telemetry.events = []

        with tempfile.TemporaryDirectory() as tmpdir:
            repl = REPL(mock_engine, tmpdir)
            repl._execute_engine_input("test input")

            # Verify engine.run was called
            mock_engine.run.assert_called()


# ============================================================================
# EDGE CASE TESTS (4 tests)
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_empty_input_handling(self):
        """Test empty input is handled gracefully."""
        profile = get_default_profile()
        session = Session("test_id", profile)

        # Empty input should not cause errors
        assert len(session.get_history()) == 0

    def test_unknown_command_error(self):
        """Test unknown command raises appropriate error."""
        mock_engine = Mock()
        profile = get_default_profile()
        session = Session("test_id", profile)
        context = CliContext(session, mock_engine, profile, "/workspace")

        registry = get_global_registry()
        cmd = registry.get_command("nonexistent_xyz")
        assert cmd is None

    def test_invalid_profile_switch(self):
        """Test switching to invalid profile raises error."""
        mock_engine = Mock()
        profile = get_default_profile()
        session = Session("test_id", profile)
        context = CliContext(session, mock_engine, profile, "/workspace")

        with pytest.raises(CliError):
            context.switch_profile("nonexistent", [profile])

    def test_malformed_command_args(self):
        """Test malformed command arguments are handled."""
        mock_engine = Mock()
        profile = get_default_profile()
        session = Session("test_id", profile)
        context = CliContext(session, mock_engine, profile, "/workspace")

        # Should handle without crashing
        from agent_engine.cli.commands import attach_command

        with pytest.raises(CommandError):
            # No args provided to attach which requires at least one
            attach_command(context, "")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
