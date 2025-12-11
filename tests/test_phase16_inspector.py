"""Tests for Phase 16: Inspector Read-Only API.

Tests read-only query methods for task inspection without mutation.
"""

import pytest
from datetime import datetime
from zoneinfo import ZoneInfo
from agent_engine.runtime.inspector import Inspector
from agent_engine.runtime.task_manager import TaskManager
from agent_engine.schemas import Task, TaskSpec, TaskLifecycle, UniversalStatus, StageExecutionRecord, NodeRole, NodeKind


class TestInspectorInitialization:
    """Tests for Inspector initialization."""

    def test_inspector_creation(self):
        """Test creating Inspector instance."""
        task_manager = TaskManager()
        inspector = Inspector(task_manager)
        assert inspector.task_manager == task_manager

    def test_inspector_with_tasks(self):
        """Test Inspector with populated task manager."""
        task_manager = TaskManager()
        spec = TaskSpec(task_spec_id="test", request="test request")
        task = task_manager.create_task(spec)

        inspector = Inspector(task_manager)
        assert inspector.get_task(task.task_id) is not None


class TestGetTask:
    """Tests for Inspector.get_task()."""

    def test_get_task_existing(self):
        """Test getting an existing task."""
        task_manager = TaskManager()
        spec = TaskSpec(task_spec_id="test", request="test request")
        task = task_manager.create_task(spec)

        inspector = Inspector(task_manager)
        retrieved = inspector.get_task(task.task_id)

        assert retrieved is not None
        assert retrieved.task_id == task.task_id
        assert retrieved.spec == task.spec

    def test_get_task_nonexistent(self):
        """Test getting a nonexistent task."""
        task_manager = TaskManager()
        inspector = Inspector(task_manager)

        result = inspector.get_task("nonexistent-task-id")
        assert result is None

    def test_get_task_returns_task_object(self):
        """Test that get_task returns Task instance."""
        task_manager = TaskManager()
        spec = TaskSpec(task_spec_id="test", request="test")
        task = task_manager.create_task(spec)

        inspector = Inspector(task_manager)
        retrieved = inspector.get_task(task.task_id)

        assert isinstance(retrieved, Task)


class TestGetTaskHistory:
    """Tests for Inspector.get_task_history()."""

    def test_get_task_history_new_task(self):
        """Test getting history of new task."""
        task_manager = TaskManager()
        spec = TaskSpec(task_spec_id="test", request="test")
        task = task_manager.create_task(spec)

        inspector = Inspector(task_manager)
        history = inspector.get_task_history(task.task_id)

        assert isinstance(history, dict)
        assert "task_id" in history
        assert "created_at" in history
        assert "stage_executions" in history
        assert history["task_id"] == task.task_id

    def test_get_task_history_nonexistent(self):
        """Test getting history of nonexistent task."""
        task_manager = TaskManager()
        inspector = Inspector(task_manager)

        history = inspector.get_task_history("nonexistent-id")
        assert history == {}

    def test_get_task_history_with_stages(self):
        """Test history includes stage executions."""
        task_manager = TaskManager()
        spec = TaskSpec(task_spec_id="test", request="test")
        task = task_manager.create_task(spec)

        # Add stage execution using legacy style
        task_manager.record_stage_result(task, "stage1", output={"result": "success"})

        inspector = Inspector(task_manager)
        history = inspector.get_task_history(task.task_id)

        assert len(history["stage_executions"]) > 0
        assert history["stage_executions"][0]["stage_id"] == "stage1"

    def test_get_task_history_fields(self):
        """Test history contains all expected fields."""
        task_manager = TaskManager()
        spec = TaskSpec(task_spec_id="test", request="test")
        task = task_manager.create_task(spec)

        inspector = Inspector(task_manager)
        history = inspector.get_task_history(task.task_id)

        expected_fields = ["task_id", "created_at", "updated_at", "current_status",
                          "status_transitions", "stage_executions"]
        for field in expected_fields:
            assert field in history


class TestGetTaskArtifacts:
    """Tests for Inspector.get_task_artifacts()."""

    def test_get_task_artifacts_empty(self):
        """Test getting artifacts from task with no artifacts."""
        task_manager = TaskManager()
        spec = TaskSpec(task_spec_id="test", request="test")
        task = task_manager.create_task(spec)

        inspector = Inspector(task_manager)
        artifacts = inspector.get_task_artifacts(task.task_id)

        assert isinstance(artifacts, dict)
        assert artifacts["task_id"] == task.task_id
        assert artifacts["artifacts"] == []

    def test_get_task_artifacts_with_output(self):
        """Test artifacts include task output."""
        task_manager = TaskManager()
        spec = TaskSpec(task_spec_id="test", request="test")
        task = task_manager.create_task(spec)
        task.current_output = {"key": "value"}

        inspector = Inspector(task_manager)
        artifacts = inspector.get_task_artifacts(task.task_id)

        assert len(artifacts["artifacts"]) > 0
        assert any(a["type"] == "task_output" for a in artifacts["artifacts"])

    def test_get_task_artifacts_with_stage_output(self):
        """Test artifacts include stage outputs."""
        task_manager = TaskManager()
        spec = TaskSpec(task_spec_id="test", request="test")
        task = task_manager.create_task(spec)

        task_manager.record_stage_result(task, "stage1", output={"stage_result": "done"})

        inspector = Inspector(task_manager)
        artifacts = inspector.get_task_artifacts(task.task_id)

        assert any(a["type"] == "stage_output" for a in artifacts["artifacts"])

    def test_get_task_artifacts_nonexistent(self):
        """Test getting artifacts for nonexistent task."""
        task_manager = TaskManager()
        inspector = Inspector(task_manager)

        artifacts = inspector.get_task_artifacts("nonexistent-id")
        assert artifacts["task_id"] == "nonexistent-id"
        assert artifacts["artifacts"] == []


class TestGetTaskEvents:
    """Tests for Inspector.get_task_events()."""

    def test_get_task_events_empty(self):
        """Test getting events from task with no errors."""
        task_manager = TaskManager()
        spec = TaskSpec(task_spec_id="test", request="test")
        task = task_manager.create_task(spec)

        inspector = Inspector(task_manager)
        events = inspector.get_task_events(task.task_id)

        assert isinstance(events, dict)
        assert events["task_id"] == task.task_id
        assert events["events"] == []

    def test_get_task_events_with_error(self):
        """Test events include execution errors."""
        task_manager = TaskManager()
        spec = TaskSpec(task_spec_id="test", request="test")
        task = task_manager.create_task(spec)

        # Create a simple error dict (not a full EngineError)
        from agent_engine.schemas import EngineError, EngineErrorCode, EngineErrorSource, Severity
        error_obj = EngineError(
            error_id="test_error",
            code=EngineErrorCode.UNKNOWN,
            message="Test error",
            source=EngineErrorSource.RUNTIME,
            severity=Severity.ERROR
        )
        task_manager.record_stage_result(task, "stage1", error=error_obj)

        inspector = Inspector(task_manager)
        events = inspector.get_task_events(task.task_id)

        assert len(events["events"]) > 0
        assert any(e["type"] == "error" for e in events["events"])

    def test_get_task_events_nonexistent(self):
        """Test getting events for nonexistent task."""
        task_manager = TaskManager()
        inspector = Inspector(task_manager)

        events = inspector.get_task_events("nonexistent-id")
        assert events["task_id"] == "nonexistent-id"
        assert events["events"] == []


class TestGetTaskSummary:
    """Tests for Inspector.get_task_summary()."""

    def test_get_task_summary_basic(self):
        """Test getting task summary."""
        task_manager = TaskManager()
        spec = TaskSpec(task_spec_id="test", request="test")
        task = task_manager.create_task(spec)

        inspector = Inspector(task_manager)
        summary = inspector.get_task_summary(task.task_id)

        assert summary is not None
        assert summary["task_id"] == task.task_id
        assert "status" in summary
        assert "created_at" in summary
        assert "duration_ms" in summary

    def test_get_task_summary_nonexistent(self):
        """Test getting summary for nonexistent task."""
        task_manager = TaskManager()
        inspector = Inspector(task_manager)

        summary = inspector.get_task_summary("nonexistent-id")
        assert summary is None

    def test_get_task_summary_fields(self):
        """Test summary contains all expected fields."""
        task_manager = TaskManager()
        spec = TaskSpec(task_spec_id="test", request="test")
        task = task_manager.create_task(spec)

        inspector = Inspector(task_manager)
        summary = inspector.get_task_summary(task.task_id)

        expected_fields = ["task_id", "status", "lifecycle", "created_at", "updated_at",
                          "duration_ms", "stage_count", "completed_stages", "has_errors",
                          "current_output"]
        for field in expected_fields:
            assert field in summary

    def test_get_task_summary_with_stages(self):
        """Test summary counts stages correctly."""
        task_manager = TaskManager()
        spec = TaskSpec(task_spec_id="test", request="test")
        task = task_manager.create_task(spec)

        # Add multiple stages using legacy style
        for i in range(3):
            task_manager.record_stage_result(task, f"stage{i}", output={"result": i})

        inspector = Inspector(task_manager)
        summary = inspector.get_task_summary(task.task_id)

        assert summary["stage_count"] == 3
        assert summary["has_errors"] is False

    def test_get_task_summary_with_errors(self):
        """Test summary detects errors."""
        task_manager = TaskManager()
        spec = TaskSpec(task_spec_id="test", request="test")
        task = task_manager.create_task(spec)

        from agent_engine.schemas import EngineError, EngineErrorCode, EngineErrorSource, Severity
        error_obj = EngineError(
            error_id="test_error",
            code=EngineErrorCode.UNKNOWN,
            message="Failed",
            source=EngineErrorSource.RUNTIME,
            severity=Severity.ERROR
        )
        task_manager.record_stage_result(task, "stage1", error=error_obj)

        inspector = Inspector(task_manager)
        summary = inspector.get_task_summary(task.task_id)

        assert summary["has_errors"] is True

    def test_get_task_summary_with_output(self):
        """Test summary includes current output."""
        task_manager = TaskManager()
        spec = TaskSpec(task_spec_id="test", request="test")
        task = task_manager.create_task(spec)
        task.current_output = {"result": "success"}

        inspector = Inspector(task_manager)
        summary = inspector.get_task_summary(task.task_id)

        assert summary["current_output"] == {"result": "success"}


class TestInspectorReadOnly:
    """Tests confirming read-only nature of Inspector."""

    def test_inspector_does_not_modify_task(self):
        """Test that inspector queries don't modify tasks."""
        task_manager = TaskManager()
        spec = TaskSpec(task_spec_id="test", request="test")
        task = task_manager.create_task(spec)
        original_status = task.status

        inspector = Inspector(task_manager)
        inspector.get_task(task.task_id)
        inspector.get_task_history(task.task_id)
        inspector.get_task_artifacts(task.task_id)
        inspector.get_task_events(task.task_id)
        inspector.get_task_summary(task.task_id)

        # Verify task is unchanged
        updated_task = task_manager.get_task(task.task_id)
        assert updated_task.status == original_status
        assert updated_task.updated_at == task.updated_at

    def test_multiple_inspector_instances(self):
        """Test multiple inspector instances see same data."""
        task_manager = TaskManager()
        spec = TaskSpec(task_spec_id="test", request="test")
        task = task_manager.create_task(spec)

        inspector1 = Inspector(task_manager)
        inspector2 = Inspector(task_manager)

        result1 = inspector1.get_task_summary(task.task_id)
        result2 = inspector2.get_task_summary(task.task_id)

        assert result1 == result2


class TestInspectorEdgeCases:
    """Tests for edge cases and error handling."""

    def test_inspector_with_empty_task_manager(self):
        """Test inspector with no tasks."""
        task_manager = TaskManager()
        inspector = Inspector(task_manager)

        assert inspector.get_task("any-id") is None
        assert inspector.get_task_history("any-id") == {}
        assert inspector.get_task_summary("any-id") is None

    def test_inspector_after_task_updates(self):
        """Test inspector sees task updates."""
        task_manager = TaskManager()
        spec = TaskSpec(task_spec_id="test", request="test")
        task = task_manager.create_task(spec)

        inspector = Inspector(task_manager)

        # Get initial summary
        summary1 = inspector.get_task_summary(task.task_id)
        initial_output = summary1["current_output"]

        # Update task
        task.current_output = {"new": "data"}

        # Get updated summary
        summary2 = inspector.get_task_summary(task.task_id)
        assert summary2["current_output"] != initial_output
        assert summary2["current_output"] == {"new": "data"}
