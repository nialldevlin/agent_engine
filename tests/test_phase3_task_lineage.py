"""Phase 3 tests: Task lineage, history, and status propagation."""

import pytest
from agent_engine.runtime.task_manager import TaskManager
from agent_engine.schemas import (
    Task,
    TaskSpec,
    TaskMode,
    TaskPriority,
    TaskLifecycle,
    UniversalStatus,
    StageExecutionRecord,
    ToolCallRecord,
)


class TestStageExecutionRecordToolTracking:
    """Test StageExecutionRecord tool_calls field."""

    def test_stage_record_has_tool_calls_field(self):
        """Test that StageExecutionRecord has tool_calls field."""
        record = StageExecutionRecord(
            output={"result": "success"},
            error=None,
            started_at="2025-01-01T00:00:00Z",
            completed_at="2025-01-01T00:01:00Z",
            tool_calls=[]
        )

        assert hasattr(record, 'tool_calls')
        assert isinstance(record.tool_calls, list)
        assert len(record.tool_calls) == 0

    def test_stage_record_stores_tool_calls(self):
        """Test that tool calls can be stored in stage record."""
        tool_call = ToolCallRecord(
            call_id="call-1",
            tool_id="search_tool",
            stage_id="stage_1",
            inputs={"query": "test"},
            output={"results": ["a", "b"]},
            started_at="2025-01-01T00:00:00Z",
            completed_at="2025-01-01T00:00:30Z"
        )

        record = StageExecutionRecord(
            output={"result": "success"},
            tool_calls=[tool_call]
        )

        assert len(record.tool_calls) == 1
        assert record.tool_calls[0].tool_id == "search_tool"
        assert record.tool_calls[0].call_id == "call-1"

    def test_stage_record_multiple_tool_calls(self):
        """Test that multiple tool calls can be tracked."""
        calls = [
            ToolCallRecord(
                call_id=f"call-{i}",
                tool_id=f"tool_{i}",
                stage_id="stage_1",
                inputs={"param": i},
                output={"result": i * 2}
            )
            for i in range(3)
        ]

        record = StageExecutionRecord(
            output={"done": True},
            tool_calls=calls
        )

        assert len(record.tool_calls) == 3
        assert [c.tool_id for c in record.tool_calls] == ["tool_0", "tool_1", "tool_2"]


class TestTaskCloneCreation:
    """Test clone creation for Branch nodes."""

    @pytest.fixture
    def task_manager(self):
        return TaskManager()

    @pytest.fixture
    def parent_task(self, task_manager):
        spec = TaskSpec(
            task_spec_id="test-spec",
            request="Test request",
            mode=TaskMode.IMPLEMENT,
            priority=TaskPriority.NORMAL
        )
        return task_manager.create_task(spec)

    def test_create_clone_generates_new_task_id(self, task_manager, parent_task):
        """Test that clone gets a unique task ID."""
        clone = task_manager.create_clone(
            parent=parent_task,
            branch_label="branch_a",
            output={"data": "test"}
        )

        assert clone.task_id != parent_task.task_id
        assert clone.task_id.startswith(f"{parent_task.task_id}-clone-")

    def test_create_clone_sets_lineage_fields(self, task_manager, parent_task):
        """Test that clone has proper lineage tracking."""
        clone = task_manager.create_clone(
            parent=parent_task,
            branch_label="branch_a"
        )

        assert clone.parent_task_id == parent_task.task_id
        assert clone.lineage_type == "clone"
        assert "branch_label" in clone.lineage_metadata
        assert clone.lineage_metadata["branch_label"] == "branch_a"

    def test_create_clone_inherits_spec(self, task_manager, parent_task):
        """Test that clone inherits parent's TaskSpec."""
        clone = task_manager.create_clone(
            parent=parent_task,
            branch_label="branch_b"
        )

        assert clone.spec.task_spec_id == parent_task.spec.task_spec_id
        assert clone.spec.request == parent_task.spec.request
        assert clone.spec.mode == parent_task.spec.mode

    def test_create_clone_inherits_memory_refs(self, task_manager, parent_task):
        """Test that clone inherits project and global memory refs."""
        clone = task_manager.create_clone(
            parent=parent_task,
            branch_label="branch_c"
        )

        # Task memory is unique per task
        assert clone.task_memory_ref != parent_task.task_memory_ref
        assert clone.task_memory_ref.startswith("task_memory:")

        # Project and global memory are inherited
        assert clone.project_memory_ref == parent_task.project_memory_ref
        assert clone.global_memory_ref == parent_task.global_memory_ref

    def test_create_clone_initializes_status(self, task_manager, parent_task):
        """Test that clone starts with QUEUED/PENDING status."""
        clone = task_manager.create_clone(
            parent=parent_task,
            branch_label="branch_d"
        )

        assert clone.lifecycle == TaskLifecycle.QUEUED
        assert clone.status == UniversalStatus.PENDING

    def test_create_clone_tracks_in_parent(self, task_manager, parent_task):
        """Test that parent tracks its clones."""
        clone1 = task_manager.create_clone(parent_task, "branch_1")
        clone2 = task_manager.create_clone(parent_task, "branch_2")

        assert len(parent_task.child_task_ids) == 2
        assert clone1.task_id in parent_task.child_task_ids
        assert clone2.task_id in parent_task.child_task_ids

    def test_create_clone_stores_in_manager(self, task_manager, parent_task):
        """Test that clone is stored in TaskManager."""
        clone = task_manager.create_clone(parent_task, "branch_e")

        assert clone.task_id in task_manager.tasks
        assert task_manager.tasks[clone.task_id] == clone

    def test_create_clone_with_output(self, task_manager, parent_task):
        """Test that clone can receive custom output."""
        output_data = {"branch": "a", "value": 42}
        clone = task_manager.create_clone(
            parent_task,
            "branch_a",
            output=output_data
        )

        assert clone.current_output == output_data

    def test_create_clone_without_output_inherits(self, task_manager, parent_task):
        """Test that clone inherits parent output if none provided."""
        parent_task.current_output = {"parent": "data"}
        clone = task_manager.create_clone(parent_task, "branch_f")

        assert clone.current_output == parent_task.current_output


class TestTaskSubtaskCreation:
    """Test subtask creation for Split nodes."""

    @pytest.fixture
    def task_manager(self):
        return TaskManager()

    @pytest.fixture
    def parent_task(self, task_manager):
        spec = TaskSpec(
            task_spec_id="test-spec",
            request="Test request",
            mode=TaskMode.IMPLEMENT,
            priority=TaskPriority.NORMAL
        )
        return task_manager.create_task(spec)

    def test_create_subtask_generates_new_task_id(self, task_manager, parent_task):
        """Test that subtask gets a unique task ID."""
        subtask = task_manager.create_subtask(
            parent=parent_task,
            subtask_input={"file": "test.py"},
            split_edge_label="file_1"
        )

        assert subtask.task_id != parent_task.task_id
        assert subtask.task_id.startswith(f"{parent_task.task_id}-subtask-")

    def test_create_subtask_sets_lineage_fields(self, task_manager, parent_task):
        """Test that subtask has proper lineage tracking."""
        subtask = task_manager.create_subtask(
            parent=parent_task,
            subtask_input={"data": "item1"}
        )

        assert subtask.parent_task_id == parent_task.task_id
        assert subtask.lineage_type == "subtask"
        assert "subtask_input" in subtask.lineage_metadata

    def test_create_subtask_creates_new_spec(self, task_manager, parent_task):
        """Test that subtask gets its own TaskSpec."""
        subtask_input = {"file": "module.py", "task": "analyze"}
        subtask = task_manager.create_subtask(
            parent=parent_task,
            subtask_input=subtask_input
        )

        # Subtask has different spec
        assert subtask.spec != parent_task.spec
        assert subtask.spec.task_spec_id != parent_task.spec.task_spec_id
        assert str(subtask_input) == subtask.spec.request

    def test_create_subtask_inherits_mode_and_priority(self, task_manager, parent_task):
        """Test that subtask inherits parent's mode and priority."""
        parent_task.spec.mode = TaskMode.REVIEW
        parent_task.spec.priority = TaskPriority.HIGH

        subtask = task_manager.create_subtask(
            parent=parent_task,
            subtask_input={"item": 1}
        )

        assert subtask.spec.mode == TaskMode.REVIEW
        assert subtask.spec.priority == TaskPriority.HIGH

    def test_create_subtask_starts_fresh(self, task_manager, parent_task):
        """Test that subtask starts with empty output."""
        parent_task.current_output = {"parent": "data"}
        subtask = task_manager.create_subtask(
            parent=parent_task,
            subtask_input={"data": "new"}
        )

        # Subtask doesn't inherit parent output
        assert subtask.current_output is None

    def test_create_subtask_tracks_in_parent(self, task_manager, parent_task):
        """Test that parent tracks its subtasks."""
        sub1 = task_manager.create_subtask(parent_task, {"item": 1})
        sub2 = task_manager.create_subtask(parent_task, {"item": 2})
        sub3 = task_manager.create_subtask(parent_task, {"item": 3})

        assert len(parent_task.child_task_ids) == 3
        assert all(s.task_id in parent_task.child_task_ids for s in [sub1, sub2, sub3])

    def test_create_subtask_stores_in_manager(self, task_manager, parent_task):
        """Test that subtask is stored in TaskManager."""
        subtask = task_manager.create_subtask(parent_task, {"data": "x"})

        assert subtask.task_id in task_manager.tasks
        assert task_manager.tasks[subtask.task_id] == subtask


class TestParentCompletionRules:
    """Test parent completion rules for clones and subtasks."""

    @pytest.fixture
    def task_manager(self):
        return TaskManager()

    @pytest.fixture
    def parent_with_clones(self, task_manager):
        spec = TaskSpec(
            task_spec_id="test",
            request="Test",
            mode=TaskMode.IMPLEMENT
        )
        parent = task_manager.create_task(spec)

        # Create 3 clones
        clone1 = task_manager.create_clone(parent, "branch_1")
        clone2 = task_manager.create_clone(parent, "branch_2")
        clone3 = task_manager.create_clone(parent, "branch_3")

        return parent, [clone1, clone2, clone3]

    @pytest.fixture
    def parent_with_subtasks(self, task_manager):
        spec = TaskSpec(
            task_spec_id="test",
            request="Test",
            mode=TaskMode.IMPLEMENT
        )
        parent = task_manager.create_task(spec)

        # Create 3 subtasks
        sub1 = task_manager.create_subtask(parent, {"item": 1})
        sub2 = task_manager.create_subtask(parent, {"item": 2})
        sub3 = task_manager.create_subtask(parent, {"item": 3})

        return parent, [sub1, sub2, sub3]

    def test_clone_completion_none_complete(self, task_manager, parent_with_clones):
        """Test that parent is not complete when no clones are complete."""
        parent, clones = parent_with_clones

        # All clones still pending
        assert not task_manager.check_clone_completion(parent.task_id)

    def test_clone_completion_one_complete(self, task_manager, parent_with_clones):
        """Test that parent completes when ONE clone succeeds."""
        parent, clones = parent_with_clones

        # Mark one clone as COMPLETED
        task_manager.set_status(clones[0], UniversalStatus.COMPLETED)

        assert task_manager.check_clone_completion(parent.task_id)

    def test_clone_completion_multiple_complete(self, task_manager, parent_with_clones):
        """Test that parent completes when multiple clones succeed."""
        parent, clones = parent_with_clones

        # Mark two clones as COMPLETED
        task_manager.set_status(clones[0], UniversalStatus.COMPLETED)
        task_manager.set_status(clones[1], UniversalStatus.COMPLETED)

        assert task_manager.check_clone_completion(parent.task_id)

    def test_clone_completion_one_failed_one_complete(self, task_manager, parent_with_clones):
        """Test that parent completes even if some clones fail."""
        parent, clones = parent_with_clones

        # One fails, one succeeds
        task_manager.set_status(clones[0], UniversalStatus.FAILED)
        task_manager.set_status(clones[1], UniversalStatus.COMPLETED)

        assert task_manager.check_clone_completion(parent.task_id)

    def test_clone_completion_all_failed(self, task_manager, parent_with_clones):
        """Test that parent doesn't complete if all clones fail."""
        parent, clones = parent_with_clones

        # All fail
        for clone in clones:
            task_manager.set_status(clone, UniversalStatus.FAILED)

        assert not task_manager.check_clone_completion(parent.task_id)

    def test_subtask_completion_none_complete(self, task_manager, parent_with_subtasks):
        """Test that parent is not complete when no subtasks are complete."""
        parent, subtasks = parent_with_subtasks

        assert not task_manager.check_subtask_completion(parent.task_id)

    def test_subtask_completion_one_complete(self, task_manager, parent_with_subtasks):
        """Test that parent doesn't complete when only ONE subtask succeeds."""
        parent, subtasks = parent_with_subtasks

        # Only one complete
        task_manager.set_status(subtasks[0], UniversalStatus.COMPLETED)

        assert not task_manager.check_subtask_completion(parent.task_id)

    def test_subtask_completion_all_complete(self, task_manager, parent_with_subtasks):
        """Test that parent completes when ALL subtasks succeed."""
        parent, subtasks = parent_with_subtasks

        # All complete
        for subtask in subtasks:
            task_manager.set_status(subtask, UniversalStatus.COMPLETED)

        assert task_manager.check_subtask_completion(parent.task_id)

    def test_subtask_completion_one_failed(self, task_manager, parent_with_subtasks):
        """Test that parent doesn't complete if ANY subtask fails."""
        parent, subtasks = parent_with_subtasks

        # Two succeed, one fails
        task_manager.set_status(subtasks[0], UniversalStatus.COMPLETED)
        task_manager.set_status(subtasks[1], UniversalStatus.COMPLETED)
        task_manager.set_status(subtasks[2], UniversalStatus.FAILED)

        assert not task_manager.check_subtask_completion(parent.task_id)

    def test_get_children_returns_all_children(self, task_manager, parent_with_clones):
        """Test that get_children returns all child tasks."""
        parent, clones = parent_with_clones

        children = task_manager.get_children(parent.task_id)

        assert len(children) == 3
        assert set(c.task_id for c in children) == set(c.task_id for c in clones)

    def test_get_children_empty_parent(self, task_manager):
        """Test that get_children returns empty list for parent with no children."""
        spec = TaskSpec(task_spec_id="test", request="Test")
        parent = task_manager.create_task(spec)

        children = task_manager.get_children(parent.task_id)

        assert children == []

    def test_get_children_mixed_lineage(self, task_manager):
        """Test get_children with both clones and subtasks."""
        spec = TaskSpec(task_spec_id="test", request="Test")
        parent = task_manager.create_task(spec)

        clone1 = task_manager.create_clone(parent, "branch_1")
        clone2 = task_manager.create_clone(parent, "branch_2")
        sub1 = task_manager.create_subtask(parent, {"item": 1})
        sub2 = task_manager.create_subtask(parent, {"item": 2})

        children = task_manager.get_children(parent.task_id)

        assert len(children) == 4
        assert sum(c.lineage_type == "clone" for c in children) == 2
        assert sum(c.lineage_type == "subtask" for c in children) == 2


class TestTaskHistoryCompleteness:
    """Test that task history is complete and deterministic."""

    @pytest.fixture
    def task_manager(self):
        return TaskManager()

    def test_stage_result_preserves_tool_calls(self, task_manager):
        """Test that recording stage results preserves tool calls."""
        spec = TaskSpec(task_spec_id="test", request="Test")
        task = task_manager.create_task(spec)

        # Create tool calls
        tool_calls = [
            ToolCallRecord(
                call_id="call-1",
                tool_id="tool_a",
                stage_id="stage_1",
                inputs={"x": 1},
                output={"y": 2}
            ),
            ToolCallRecord(
                call_id="call-2",
                tool_id="tool_b",
                stage_id="stage_1",
                inputs={"x": 2},
                output={"y": 4}
            )
        ]

        # Record stage with tool calls
        record = StageExecutionRecord(
            output={"result": "done"},
            tool_calls=tool_calls,
            started_at="2025-01-01T00:00:00Z",
            completed_at="2025-01-01T00:01:00Z"
        )

        task.stage_results["stage_1"] = record

        # Verify preservation
        stored_record = task.stage_results["stage_1"]
        assert len(stored_record.tool_calls) == 2
        assert stored_record.tool_calls[0].tool_id == "tool_a"
        assert stored_record.tool_calls[1].tool_id == "tool_b"

    def test_lineage_metadata_preserved_through_serialization(self, task_manager):
        """Test that lineage metadata survives to_dict/from_dict cycle."""
        spec = TaskSpec(task_spec_id="test", request="Test")
        parent = task_manager.create_task(spec)

        clone = task_manager.create_clone(parent, "branch_x", output={"data": 123})

        # Serialize and deserialize
        clone_dict = clone.to_dict()
        restored_clone = Task.from_dict(clone_dict)

        # Verify all lineage fields preserved
        assert restored_clone.parent_task_id == parent.task_id
        assert restored_clone.lineage_type == "clone"
        assert "branch_label" in restored_clone.lineage_metadata
        assert restored_clone.lineage_metadata["branch_label"] == "branch_x"
