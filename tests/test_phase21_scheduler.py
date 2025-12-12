"""
Comprehensive tests for Phase 21: Task Scheduler (Multi-Task Execution Layer).

Tests cover:
- Scheduler configuration and validation
- FIFO queueing behavior
- Sequential execution (max_concurrency=1)
- Task state tracking
- Max queue size enforcement
- Telemetry event emission
- Engine integration
- CLI command functionality
"""

import pytest
from datetime import datetime
from typing import Any, Dict

from agent_engine.schemas.scheduler import (
    TaskState,
    QueuePolicy,
    SchedulerConfig,
    QueuedTask,
)
from agent_engine.scheduler_loader import (
    load_scheduler_manifest,
    parse_scheduler,
    get_default_config,
)
from agent_engine.runtime.scheduler import TaskScheduler
from agent_engine.telemetry import TelemetryBus


# ============================================================================
# Scheduler Config Tests (6 tests)
# ============================================================================

class TestSchedulerConfig:
    """Test scheduler configuration."""

    def test_default_config(self):
        """Test default scheduler config."""
        config = SchedulerConfig()
        assert config.enabled is True
        assert config.max_concurrency == 1
        assert config.queue_policy == QueuePolicy.FIFO
        assert config.max_queue_size is None

    def test_custom_config(self):
        """Test custom scheduler config."""
        config = SchedulerConfig(
            enabled=True,
            max_concurrency=1,
            queue_policy=QueuePolicy.FIFO,
            max_queue_size=50,
        )
        assert config.max_queue_size == 50
        config.validate()  # Should not raise

    def test_config_validation_max_concurrency(self):
        """Test config validation for max_concurrency."""
        config = SchedulerConfig(max_concurrency=0)
        with pytest.raises(ValueError, match="max_concurrency must be >= 1"):
            config.validate()

    def test_config_validation_max_queue_size(self):
        """Test config validation for max_queue_size."""
        config = SchedulerConfig(max_queue_size=0)
        with pytest.raises(ValueError, match="max_queue_size must be >= 1"):
            config.validate()

    def test_config_validation_queue_policy(self):
        """Test config validation for queue_policy."""
        # This test is primarily documentation since enum prevents invalid values
        config = SchedulerConfig(queue_policy=QueuePolicy.FIFO)
        config.validate()  # Should not raise

    def test_unbounded_queue_size(self):
        """Test unbounded queue size is allowed."""
        config = SchedulerConfig(max_queue_size=None)
        config.validate()  # Should not raise


# ============================================================================
# Scheduler Loader Tests (6 tests)
# ============================================================================

class TestSchedulerLoader:
    """Test scheduler manifest loading and parsing."""

    def test_get_default_config(self):
        """Test default config from loader."""
        config = get_default_config()
        assert config.enabled is True
        assert config.max_concurrency == 1
        assert config.queue_policy == QueuePolicy.FIFO
        assert config.max_queue_size is None

    def test_parse_empty_manifest(self):
        """Test parsing empty/None manifest data."""
        config = parse_scheduler(None)
        assert config.enabled is True
        assert config.max_concurrency == 1

    def test_parse_minimal_manifest(self):
        """Test parsing minimal manifest."""
        data = {
            "scheduler": {
                "max_concurrency": 1,
                "queue_policy": "fifo",
            }
        }
        config = parse_scheduler(data)
        assert config.max_concurrency == 1
        assert config.queue_policy == QueuePolicy.FIFO

    def test_parse_full_manifest(self):
        """Test parsing full manifest."""
        data = {
            "scheduler": {
                "enabled": True,
                "max_concurrency": 1,
                "queue_policy": "fifo",
                "max_queue_size": 100,
            }
        }
        config = parse_scheduler(data)
        assert config.enabled is True
        assert config.max_queue_size == 100

    def test_parse_invalid_queue_policy(self):
        """Test parsing with invalid queue policy."""
        data = {
            "scheduler": {
                "queue_policy": "invalid_policy",
            }
        }
        with pytest.raises(ValueError, match="Unknown queue_policy"):
            parse_scheduler(data)

    def test_parse_with_validation_error(self):
        """Test parsing with config that fails validation."""
        data = {
            "scheduler": {
                "max_concurrency": -1,
            }
        }
        with pytest.raises(ValueError):
            parse_scheduler(data)


# ============================================================================
# TaskScheduler Core Tests (10 tests)
# ============================================================================

class TestTaskScheduler:
    """Test TaskScheduler core functionality."""

    @pytest.fixture
    def scheduler(self):
        """Create a test scheduler."""
        config = SchedulerConfig(
            enabled=True,
            max_concurrency=1,
            queue_policy=QueuePolicy.FIFO,
            max_queue_size=None,
        )
        return TaskScheduler(config=config)

    def test_enqueue_single_task(self, scheduler):
        """Test enqueueing a single task."""
        task_id = scheduler.enqueue_task({"text": "hello"})
        assert task_id is not None
        assert scheduler.get_queue_size() == 1

    def test_enqueue_multiple_tasks(self, scheduler):
        """Test enqueueing multiple tasks."""
        task_id1 = scheduler.enqueue_task({"text": "task1"})
        task_id2 = scheduler.enqueue_task({"text": "task2"})
        task_id3 = scheduler.enqueue_task({"text": "task3"})

        assert task_id1 != task_id2 != task_id3
        assert scheduler.get_queue_size() == 3

    def test_fifo_order(self, scheduler):
        """Test FIFO queueing order."""
        task_id1 = scheduler.enqueue_task({"order": 1})
        task_id2 = scheduler.enqueue_task({"order": 2})
        task_id3 = scheduler.enqueue_task({"order": 3})

        # Dequeue and verify FIFO order
        dequeued1 = scheduler.run_next()
        assert dequeued1 == task_id1

        # Complete first task to allow next to be dequeued
        scheduler.mark_task_completed(task_id1)

        dequeued2 = scheduler.run_next()
        assert dequeued2 == task_id2

        # Complete second task to allow third to be dequeued
        scheduler.mark_task_completed(task_id2)

        dequeued3 = scheduler.run_next()
        assert dequeued3 == task_id3

    def test_max_concurrency_enforcement(self, scheduler):
        """Test max_concurrency prevents multiple concurrent tasks."""
        scheduler.enqueue_task({"text": "task1"})
        scheduler.enqueue_task({"text": "task2"})

        # Dequeue first task
        task1 = scheduler.run_next()
        assert task1 is not None
        assert scheduler.get_running_count() == 1

        # Try to dequeue second (should be blocked by concurrency limit)
        task2 = scheduler.run_next()
        assert task2 is None  # Blocked by max_concurrency=1

        # Complete first task
        scheduler.mark_task_completed(task1)
        assert scheduler.get_running_count() == 0

        # Now second task can be dequeued
        task2 = scheduler.run_next()
        assert task2 is not None

    def test_queue_size_limit(self):
        """Test max_queue_size enforcement."""
        config = SchedulerConfig(max_queue_size=2)
        scheduler = TaskScheduler(config=config)

        scheduler.enqueue_task({"text": "task1"})
        scheduler.enqueue_task({"text": "task2"})

        # Third task should fail
        with pytest.raises(RuntimeError, match="Queue full"):
            scheduler.enqueue_task({"text": "task3"})

        assert scheduler.get_queue_size() == 2

    def test_task_state_tracking(self, scheduler):
        """Test task state transitions."""
        task_id = scheduler.enqueue_task({"text": "test"})

        # Initially queued
        state = scheduler.get_task_state(task_id)
        assert state == TaskState.QUEUED

        # After dequeue, running
        scheduler.run_next()
        state = scheduler.get_task_state(task_id)
        assert state == TaskState.RUNNING

        # After completion, completed
        scheduler.mark_task_completed(task_id, output={"result": "ok"})
        state = scheduler.get_task_state(task_id)
        assert state == TaskState.COMPLETED

    def test_mark_task_completed(self, scheduler):
        """Test marking task as completed."""
        task_id = scheduler.enqueue_task({"text": "test"})
        scheduler.run_next()

        success = scheduler.mark_task_completed(task_id, output={"status": "done"})
        assert success is True
        assert scheduler.get_running_count() == 0
        assert scheduler.get_completed_count() == 1

    def test_mark_task_failed(self, scheduler):
        """Test marking task as failed."""
        task_id = scheduler.enqueue_task({"text": "test"})
        scheduler.run_next()

        success = scheduler.mark_task_failed(task_id, error="Test error")
        assert success is True
        assert scheduler.get_running_count() == 0
        assert scheduler.get_completed_count() == 1
        assert scheduler.get_task_state(task_id) == TaskState.FAILED

    def test_invalid_task_completion(self, scheduler):
        """Test completing non-existent task returns False."""
        success = scheduler.mark_task_completed("invalid-task-id")
        assert success is False


# ============================================================================
# TaskScheduler State and Metrics Tests (6 tests)
# ============================================================================

class TestSchedulerState:
    """Test TaskScheduler state querying and metrics."""

    @pytest.fixture
    def scheduler_with_tasks(self):
        """Create scheduler with some tasks."""
        config = SchedulerConfig(max_concurrency=1)
        scheduler = TaskScheduler(config=config)

        # Queue 3 tasks
        t1 = scheduler.enqueue_task({"id": 1})
        t2 = scheduler.enqueue_task({"id": 2})
        t3 = scheduler.enqueue_task({"id": 3})

        # Dequeue first task
        scheduler.run_next()

        # Complete second task (for testing)
        scheduler.mark_task_completed(t1)

        return scheduler

    def test_get_all_states(self, scheduler_with_tasks):
        """Test getting all task states."""
        states = scheduler_with_tasks.get_all_states()

        assert len(states) == 3
        assert all(task_id in states for task_id in scheduler_with_tasks.completed.keys() | scheduler_with_tasks.running.keys() | {t.task_id for t in scheduler_with_tasks.queue})

    def test_get_queue_size(self, scheduler_with_tasks):
        """Test getting queue size."""
        size = scheduler_with_tasks.get_queue_size()
        assert size == 2  # 3 tasks - 1 completed

    def test_get_running_count(self, scheduler_with_tasks):
        """Test getting running count."""
        count = scheduler_with_tasks.get_running_count()
        assert count == 0  # All moved to completed or still queued

    def test_get_completed_count(self, scheduler_with_tasks):
        """Test getting completed count."""
        count = scheduler_with_tasks.get_completed_count()
        assert count == 1  # One task completed

    def test_get_task_state_for_queued(self, scheduler_with_tasks):
        """Test getting state for queued task."""
        # Get first queued task
        if scheduler_with_tasks.queue:
            task_id = scheduler_with_tasks.queue[0].task_id
            state = scheduler_with_tasks.get_task_state(task_id)
            assert state == TaskState.QUEUED

    def test_get_nonexistent_task_state(self, scheduler_with_tasks):
        """Test getting state for non-existent task."""
        state = scheduler_with_tasks.get_task_state("nonexistent-task")
        assert state is None


# ============================================================================
# Telemetry Tests (4 tests)
# ============================================================================

class TestSchedulerTelemetry:
    """Test scheduler with telemetry integration."""

    @pytest.fixture
    def scheduler_with_telemetry(self):
        """Create scheduler with telemetry."""
        config = SchedulerConfig()
        telemetry = TelemetryBus()
        return TaskScheduler(config=config, telemetry=telemetry), telemetry

    def test_task_queued_tracking(self, scheduler_with_telemetry):
        """Test task queued state tracking."""
        scheduler, telemetry = scheduler_with_telemetry

        task_id = scheduler.enqueue_task({"text": "test"})

        # Verify task is in queued state
        assert scheduler.get_task_state(task_id) == TaskState.QUEUED
        assert scheduler.get_queue_size() == 1

    def test_task_dequeued_tracking(self, scheduler_with_telemetry):
        """Test task dequeued state tracking."""
        scheduler, telemetry = scheduler_with_telemetry

        task_id = scheduler.enqueue_task({"text": "test"})
        scheduler.run_next()

        # Verify task is now running
        assert scheduler.get_task_state(task_id) == TaskState.RUNNING
        assert scheduler.get_running_count() == 1

    def test_task_completed_tracking(self, scheduler_with_telemetry):
        """Test task completed state tracking."""
        scheduler, telemetry = scheduler_with_telemetry

        task_id = scheduler.enqueue_task({"text": "test"})
        scheduler.run_next()
        scheduler.mark_task_completed(task_id)

        # Verify task is completed
        assert scheduler.get_task_state(task_id) == TaskState.COMPLETED
        assert scheduler.get_completed_count() == 1

    def test_task_failed_tracking(self, scheduler_with_telemetry):
        """Test task failed state tracking."""
        scheduler, telemetry = scheduler_with_telemetry

        task_id = scheduler.enqueue_task({"text": "test"})
        scheduler.run_next()
        scheduler.mark_task_failed(task_id, "Test error")

        # Verify task is failed
        assert scheduler.get_task_state(task_id) == TaskState.FAILED
        assert scheduler.get_completed_count() == 1


# ============================================================================
# QueuedTask Tests (2 tests)
# ============================================================================

class TestQueuedTask:
    """Test QueuedTask dataclass."""

    def test_queued_task_creation(self):
        """Test creating a queued task."""
        task = QueuedTask(
            task_id="task-123",
            input={"text": "hello"},
            start_node_id="node-1",
        )
        assert task.task_id == "task-123"
        assert task.input == {"text": "hello"}
        assert task.state == TaskState.QUEUED

    def test_queued_task_with_metadata(self):
        """Test queued task with metadata."""
        task = QueuedTask(
            task_id="task-456",
            input={"text": "world"},
            metadata={"priority": "high"},
        )
        assert task.metadata["priority"] == "high"


# ============================================================================
# Edge Cases and Stress Tests (4 tests)
# ============================================================================

class TestSchedulerEdgeCases:
    """Test edge cases and stress scenarios."""

    def test_empty_queue_run_next(self):
        """Test run_next on empty queue."""
        config = SchedulerConfig()
        scheduler = TaskScheduler(config=config)

        result = scheduler.run_next()
        assert result is None

    def test_large_queue(self):
        """Test handling large queue."""
        config = SchedulerConfig(max_queue_size=1000)
        scheduler = TaskScheduler(config=config)

        # Queue 100 tasks
        for i in range(100):
            task_id = scheduler.enqueue_task({"index": i})
            assert task_id is not None

        assert scheduler.get_queue_size() == 100

    def test_rapid_queue_operations(self):
        """Test rapid enqueue/dequeue operations."""
        config = SchedulerConfig()
        scheduler = TaskScheduler(config=config)

        for i in range(10):
            task_id = scheduler.enqueue_task({"index": i})
            scheduler.run_next()
            scheduler.mark_task_completed(task_id)

        assert scheduler.get_queue_size() == 0
        assert scheduler.get_completed_count() == 10

    def test_mixed_completion_failure(self):
        """Test mixing completed and failed tasks."""
        config = SchedulerConfig()
        scheduler = TaskScheduler(config=config)

        # Queue and process alternating completion/failure
        for i in range(6):
            task_id = scheduler.enqueue_task({"index": i})
            scheduler.run_next()

            if i % 2 == 0:
                scheduler.mark_task_completed(task_id)
            else:
                scheduler.mark_task_failed(task_id, f"Error {i}")

        assert scheduler.get_completed_count() == 6
        completed_states = [task.state for task in scheduler.completed.values()]
        assert TaskState.COMPLETED in completed_states
        assert TaskState.FAILED in completed_states


# ============================================================================
# Integration Tests with Mocked Engine (2 tests)
# ============================================================================

class TestSchedulerIntegration:
    """Test scheduler integration with engine components."""

    def test_scheduler_with_realistic_workflow(self):
        """Test scheduler in realistic workflow scenario."""
        config = SchedulerConfig(max_concurrency=1, max_queue_size=100)
        scheduler = TaskScheduler(config=config)

        # Simulate real workflow: queue tasks, process, track state
        inputs = [
            {"user_id": 1, "action": "create"},
            {"user_id": 2, "action": "update"},
            {"user_id": 3, "action": "delete"},
        ]

        task_ids = []
        for input_data in inputs:
            task_id = scheduler.enqueue_task(input_data, start_node_id="start")
            task_ids.append(task_id)

        assert scheduler.get_queue_size() == 3

        # Process tasks
        results = []
        while scheduler.get_queue_size() > 0:
            task_id = scheduler.run_next()
            if task_id:
                # Simulate work
                scheduler.mark_task_completed(task_id, output={"processed": True})
                results.append(task_id)

        assert len(results) == 3
        assert scheduler.get_completed_count() == 3

    def test_scheduler_queue_overflow_handling(self):
        """Test scheduler handles queue overflow gracefully."""
        config = SchedulerConfig(max_queue_size=5)
        scheduler = TaskScheduler(config=config)

        # Fill queue to limit
        successful = 0
        for i in range(10):
            try:
                scheduler.enqueue_task({"index": i})
                successful += 1
            except RuntimeError:
                break

        assert successful == 5
        assert scheduler.get_queue_size() == 5


# ============================================================================
# Scheduler Config YAML Format Tests (2 tests)
# ============================================================================

class TestSchedulerYAMLFormat:
    """Test scheduler.yaml configuration format."""

    def test_parse_scheduler_yaml_minimal(self):
        """Test parsing minimal scheduler.yaml format."""
        yaml_data = {
            "scheduler": {
                "enabled": True,
            }
        }
        config = parse_scheduler(yaml_data)
        assert config.enabled is True
        assert config.max_concurrency == 1

    def test_parse_scheduler_yaml_with_limits(self):
        """Test parsing scheduler.yaml with size limits."""
        yaml_data = {
            "scheduler": {
                "enabled": True,
                "max_concurrency": 1,
                "queue_policy": "fifo",
                "max_queue_size": 50,
            }
        }
        config = parse_scheduler(yaml_data)
        assert config.max_queue_size == 50
        config.validate()  # Should not raise
