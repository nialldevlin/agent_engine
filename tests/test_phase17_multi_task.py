"""Tests for Phase 17: Multi-Task Query Methods.

Tests multi-task execution, task management, and isolation guarantees.
"""

import pytest
from agent_engine.runtime.task_manager import TaskManager
from agent_engine.schemas import Task, TaskSpec, UniversalStatus


class TestTaskManagerGetAll:
    """Tests for get_all_tasks() method."""

    def test_get_all_tasks_empty(self):
        """Test get_all_tasks with no tasks."""
        task_manager = TaskManager()
        tasks = task_manager.get_all_tasks()
        assert isinstance(tasks, list)
        assert len(tasks) == 0

    def test_get_all_tasks_single(self):
        """Test get_all_tasks with one task."""
        task_manager = TaskManager()
        spec = TaskSpec(task_spec_id="test", request="test request")
        task = task_manager.create_task(spec)

        tasks = task_manager.get_all_tasks()
        assert len(tasks) == 1
        assert tasks[0].task_id == task.task_id

    def test_get_all_tasks_multiple(self):
        """Test get_all_tasks with multiple tasks."""
        task_manager = TaskManager()
        created_tasks = []

        for i in range(5):
            spec = TaskSpec(task_spec_id=f"test{i}", request=f"request{i}")
            task = task_manager.create_task(spec)
            created_tasks.append(task)

        all_tasks = task_manager.get_all_tasks()
        assert len(all_tasks) == 5

        # Verify all created tasks are in result
        all_task_ids = {t.task_id for t in all_tasks}
        for task in created_tasks:
            assert task.task_id in all_task_ids

    def test_get_all_tasks_returns_task_objects(self):
        """Test get_all_tasks returns Task instances."""
        task_manager = TaskManager()
        spec = TaskSpec(task_spec_id="test", request="test")
        task_manager.create_task(spec)

        all_tasks = task_manager.get_all_tasks()
        assert all(isinstance(t, Task) for t in all_tasks)


class TestTaskManagerByStatus:
    """Tests for get_tasks_by_status() method."""

    def test_get_tasks_by_status_empty(self):
        """Test get_tasks_by_status with no matching tasks."""
        task_manager = TaskManager()
        spec = TaskSpec(task_spec_id="test", request="test")
        task = task_manager.create_task(spec)

        # Task is PENDING, query for COMPLETED
        completed = task_manager.get_tasks_by_status(UniversalStatus.COMPLETED)
        assert len(completed) == 0

    def test_get_tasks_by_status_pending(self):
        """Test get_tasks_by_status for PENDING status."""
        task_manager = TaskManager()

        for i in range(3):
            spec = TaskSpec(task_spec_id=f"test{i}", request=f"request{i}")
            task_manager.create_task(spec)

        pending = task_manager.get_tasks_by_status(UniversalStatus.PENDING)
        assert len(pending) == 3

    def test_get_tasks_by_status_mixed(self):
        """Test get_tasks_by_status with mixed task statuses."""
        task_manager = TaskManager()

        # Create tasks
        spec1 = TaskSpec(task_spec_id="test1", request="request1")
        task1 = task_manager.create_task(spec1)

        spec2 = TaskSpec(task_spec_id="test2", request="request2")
        task2 = task_manager.create_task(spec2)

        # Change statuses
        task_manager.set_status(task1, UniversalStatus.COMPLETED)
        # task2 remains PENDING

        completed = task_manager.get_tasks_by_status(UniversalStatus.COMPLETED)
        pending = task_manager.get_tasks_by_status(UniversalStatus.PENDING)

        assert len(completed) == 1
        assert len(pending) == 1
        assert completed[0].task_id == task1.task_id
        assert pending[0].task_id == task2.task_id

    def test_get_tasks_by_status_returns_correct_type(self):
        """Test get_tasks_by_status returns Task instances."""
        task_manager = TaskManager()
        spec = TaskSpec(task_spec_id="test", request="test")
        task = task_manager.create_task(spec)

        pending = task_manager.get_tasks_by_status(UniversalStatus.PENDING)
        assert all(isinstance(t, Task) for t in pending)


class TestTaskManagerCount:
    """Tests for get_task_count() method."""

    def test_get_task_count_empty(self):
        """Test get_task_count with no tasks."""
        task_manager = TaskManager()
        count = task_manager.get_task_count()
        assert count == 0

    def test_get_task_count_single(self):
        """Test get_task_count with one task."""
        task_manager = TaskManager()
        spec = TaskSpec(task_spec_id="test", request="test")
        task_manager.create_task(spec)

        count = task_manager.get_task_count()
        assert count == 1

    def test_get_task_count_multiple(self):
        """Test get_task_count with multiple tasks."""
        task_manager = TaskManager()

        for i in range(10):
            spec = TaskSpec(task_spec_id=f"test{i}", request=f"request{i}")
            task_manager.create_task(spec)

        count = task_manager.get_task_count()
        assert count == 10

    def test_get_task_count_after_updates(self):
        """Test get_task_count after task status changes."""
        task_manager = TaskManager()

        spec = TaskSpec(task_spec_id="test", request="test")
        task = task_manager.create_task(spec)

        # Count doesn't change when status changes
        initial_count = task_manager.get_task_count()
        task_manager.set_status(task, UniversalStatus.COMPLETED)
        final_count = task_manager.get_task_count()

        assert initial_count == final_count == 1


class TestTaskManagerClearCompleted:
    """Tests for clear_completed_tasks() method."""

    def test_clear_completed_tasks_empty(self):
        """Test clear_completed_tasks with no completed tasks."""
        task_manager = TaskManager()
        spec = TaskSpec(task_spec_id="test", request="test")
        task_manager.create_task(spec)

        removed = task_manager.clear_completed_tasks()
        assert removed == 0
        assert task_manager.get_task_count() == 1

    def test_clear_completed_tasks_all_pending(self):
        """Test clear_completed_tasks with all pending tasks."""
        task_manager = TaskManager()

        for i in range(3):
            spec = TaskSpec(task_spec_id=f"test{i}", request=f"request{i}")
            task_manager.create_task(spec)

        removed = task_manager.clear_completed_tasks()
        assert removed == 0
        assert task_manager.get_task_count() == 3

    def test_clear_completed_tasks_some_completed(self):
        """Test clear_completed_tasks with mixed statuses."""
        task_manager = TaskManager()

        spec1 = TaskSpec(task_spec_id="test1", request="request1")
        task1 = task_manager.create_task(spec1)

        spec2 = TaskSpec(task_spec_id="test2", request="request2")
        task2 = task_manager.create_task(spec2)

        spec3 = TaskSpec(task_spec_id="test3", request="request3")
        task3 = task_manager.create_task(spec3)

        # Complete 2 tasks
        task_manager.set_status(task1, UniversalStatus.COMPLETED)
        task_manager.set_status(task3, UniversalStatus.COMPLETED)

        removed = task_manager.clear_completed_tasks()
        assert removed == 2
        assert task_manager.get_task_count() == 1

        # Verify pending task remains
        remaining = task_manager.get_all_tasks()
        assert remaining[0].task_id == task2.task_id

    def test_clear_completed_tasks_all_completed(self):
        """Test clear_completed_tasks with all completed tasks."""
        task_manager = TaskManager()

        for i in range(5):
            spec = TaskSpec(task_spec_id=f"test{i}", request=f"request{i}")
            task = task_manager.create_task(spec)
            task_manager.set_status(task, UniversalStatus.COMPLETED)

        removed = task_manager.clear_completed_tasks()
        assert removed == 5
        assert task_manager.get_task_count() == 0

    def test_clear_completed_tasks_leaves_other_statuses(self):
        """Test clear_completed_tasks preserves non-completed tasks."""
        task_manager = TaskManager()

        spec1 = TaskSpec(task_spec_id="test1", request="request1")
        task1 = task_manager.create_task(spec1)

        spec2 = TaskSpec(task_spec_id="test2", request="request2")
        task2 = task_manager.create_task(spec2)

        spec3 = TaskSpec(task_spec_id="test3", request="request3")
        task3 = task_manager.create_task(spec3)

        # Set various statuses
        task_manager.set_status(task1, UniversalStatus.COMPLETED)
        task_manager.set_status(task2, UniversalStatus.IN_PROGRESS)
        task_manager.set_status(task3, UniversalStatus.FAILED)

        removed = task_manager.clear_completed_tasks()
        assert removed == 1

        # Verify IN_PROGRESS and FAILED remain
        remaining = task_manager.get_all_tasks()
        remaining_ids = {t.task_id for t in remaining}
        assert task2.task_id in remaining_ids
        assert task3.task_id in remaining_ids
        assert task1.task_id not in remaining_ids


class TestMultiTaskIsolation:
    """Tests for task isolation guarantees."""

    def test_task_id_uniqueness(self):
        """Test that each task gets a unique ID."""
        task_manager = TaskManager()

        task_ids = []
        for i in range(10):
            spec = TaskSpec(task_spec_id=f"test{i}", request=f"request{i}")
            task = task_manager.create_task(spec)
            task_ids.append(task.task_id)

        # All IDs should be unique
        assert len(task_ids) == len(set(task_ids))

    def test_task_memory_refs_unique(self):
        """Test that each task gets unique task memory references."""
        task_manager = TaskManager()

        task1_spec = TaskSpec(task_spec_id="test1", request="request1")
        task1 = task_manager.create_task(task1_spec)

        task2_spec = TaskSpec(task_spec_id="test2", request="request2")
        task2 = task_manager.create_task(task2_spec)

        # Task memory refs should be unique (based on unique task IDs)
        assert task1.task_memory_ref != task2.task_memory_ref

        # Global memory should match
        assert task1.global_memory_ref == task2.global_memory_ref

        # Project memory refs will be based on extracted project_id from task_id
        # Both should have valid project refs (format: project_memory:{project_id})
        assert task1.project_memory_ref.startswith("project_memory:")
        assert task2.project_memory_ref.startswith("project_memory:")

    def test_task_state_independence(self):
        """Test that task state changes don't affect other tasks."""
        task_manager = TaskManager()

        spec1 = TaskSpec(task_spec_id="test1", request="request1")
        task1 = task_manager.create_task(spec1)

        spec2 = TaskSpec(task_spec_id="test2", request="request2")
        task2 = task_manager.create_task(spec2)

        # Modify task1
        task_manager.set_status(task1, UniversalStatus.COMPLETED)
        task_manager.update_task_output(task1.task_id, {"result": "success"})

        # task2 should be unchanged
        task2_retrieved = task_manager.get_task(task2.task_id)
        assert task2_retrieved.status == UniversalStatus.PENDING
        assert task2_retrieved.current_output is None

    def test_multi_task_queries_no_modification(self):
        """Test that queries don't modify task state."""
        task_manager = TaskManager()

        spec = TaskSpec(task_spec_id="test", request="test")
        task = task_manager.create_task(spec)
        original_status = task.status
        original_updated_at = task.updated_at

        # Query all tasks multiple times
        task_manager.get_all_tasks()
        task_manager.get_all_tasks()
        task_manager.get_task_count()
        task_manager.get_tasks_by_status(UniversalStatus.PENDING)

        # Task should be unchanged
        updated_task = task_manager.get_task(task.task_id)
        assert updated_task.status == original_status
        assert updated_task.updated_at == original_updated_at


class TestMultiTaskWorkflow:
    """Tests for multi-task workflow patterns."""

    def test_sequential_task_creation(self):
        """Test creating and tracking multiple sequential tasks."""
        task_manager = TaskManager()

        results = []
        for i in range(3):
            spec = TaskSpec(task_spec_id=f"query{i}", request=f"What is {i}?")
            task = task_manager.create_task(spec)
            results.append(task)

            # Simulate execution
            task_manager.set_status(task, UniversalStatus.IN_PROGRESS)
            task_manager.update_task_output(task.task_id, {"answer": i * 10})
            task_manager.set_status(task, UniversalStatus.COMPLETED)

        # Verify all tasks tracked
        all_tasks = task_manager.get_all_tasks()
        assert len(all_tasks) == 3

        # Verify all completed
        completed = task_manager.get_tasks_by_status(UniversalStatus.COMPLETED)
        assert len(completed) == 3

    def test_task_filtering_by_status(self):
        """Test filtering tasks by status for monitoring."""
        task_manager = TaskManager()

        # Create 10 tasks
        for i in range(10):
            spec = TaskSpec(task_spec_id=f"test{i}", request=f"request{i}")
            task = task_manager.create_task(spec)

            # Assign different statuses
            if i < 3:
                task_manager.set_status(task, UniversalStatus.COMPLETED)
            elif i < 6:
                task_manager.set_status(task, UniversalStatus.IN_PROGRESS)
            # Rest remain PENDING

        # Query by status
        completed = task_manager.get_tasks_by_status(UniversalStatus.COMPLETED)
        in_progress = task_manager.get_tasks_by_status(UniversalStatus.IN_PROGRESS)
        pending = task_manager.get_tasks_by_status(UniversalStatus.PENDING)

        assert len(completed) == 3
        assert len(in_progress) == 3
        assert len(pending) == 4

    def test_memory_management_workflow(self):
        """Test memory cleanup workflow."""
        task_manager = TaskManager()

        # Create 20 tasks
        for i in range(20):
            spec = TaskSpec(task_spec_id=f"test{i}", request=f"request{i}")
            task = task_manager.create_task(spec)

            # Complete half of them
            if i < 10:
                task_manager.set_status(task, UniversalStatus.COMPLETED)

        # Before cleanup
        assert task_manager.get_task_count() == 20

        # Clear completed tasks
        removed = task_manager.clear_completed_tasks()
        assert removed == 10

        # After cleanup
        assert task_manager.get_task_count() == 10
        remaining = task_manager.get_all_tasks()
        assert all(t.status != UniversalStatus.COMPLETED for t in remaining)


class TestTaskManagerEdgeCases:
    """Tests for edge cases in task management."""

    def test_get_all_tasks_after_clear(self):
        """Test get_all_tasks after clearing completed tasks."""
        task_manager = TaskManager()

        for i in range(5):
            spec = TaskSpec(task_spec_id=f"test{i}", request=f"request{i}")
            task = task_manager.create_task(spec)
            if i % 2 == 0:
                task_manager.set_status(task, UniversalStatus.COMPLETED)

        task_manager.clear_completed_tasks()

        all_tasks = task_manager.get_all_tasks()
        assert all(t.status != UniversalStatus.COMPLETED for t in all_tasks)

    def test_multiple_clears_idempotent(self):
        """Test that multiple clear calls are safe."""
        task_manager = TaskManager()

        for i in range(3):
            spec = TaskSpec(task_spec_id=f"test{i}", request=f"request{i}")
            task = task_manager.create_task(spec)
            task_manager.set_status(task, UniversalStatus.COMPLETED)

        # Clear twice
        removed1 = task_manager.clear_completed_tasks()
        removed2 = task_manager.clear_completed_tasks()

        assert removed1 == 3
        assert removed2 == 0
        assert task_manager.get_task_count() == 0

    def test_task_count_consistency(self):
        """Test that task count stays consistent with task tracking."""
        task_manager = TaskManager()

        for i in range(10):
            spec = TaskSpec(task_spec_id=f"test{i}", request=f"request{i}")
            task_manager.create_task(spec)

        # Count should match all_tasks length
        count = task_manager.get_task_count()
        all_tasks = task_manager.get_all_tasks()
        assert count == len(all_tasks)

        # Count should match sum of status-filtered tasks
        pending = len(task_manager.get_tasks_by_status(UniversalStatus.PENDING))
        assert count == pending
