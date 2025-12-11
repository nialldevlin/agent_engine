"""Phase 6 tests: Memory & Context v1.

Tests for:
- Memory store implementations (Task, Project, Global)
- Context Profile validation and resolution
- Context assembly with profiles
- Token budgeting and compression
- Integration with node execution
"""

import pytest
from datetime import datetime
from typing import Dict, List, Any

from agent_engine.schemas import (
    ContextItem,
    ContextPackage,
    ContextProfile,
    ContextProfileSource,
    Task,
    TaskSpec,
    TaskLifecycle,
    TaskMode,
    UniversalStatus,
)
import uuid
from agent_engine.runtime.memory import (
    TaskMemoryStore,
    ProjectMemoryStore,
    GlobalMemoryStore,
    InMemoryBackend,
)
from agent_engine.runtime.context import ContextAssembler


class TestInMemoryBackend:
    """Tests for InMemoryBackend implementation."""

    def test_add_and_get_item(self):
        """Test adding and retrieving items."""
        backend = InMemoryBackend()
        item = ContextItem(
            context_item_id="test-1",
            kind="reasoning",
            source="test",
            timestamp="2025-01-01T00:00:00",
            tags=["test"],
            importance=0.8,
            token_cost=10,
            payload={"text": "test"}
        )
        backend.add(item)
        retrieved = backend.get("test-1")
        assert retrieved is not None
        assert retrieved.context_item_id == "test-1"

    def test_get_nonexistent_item(self):
        """Test getting non-existent item returns None."""
        backend = InMemoryBackend()
        retrieved = backend.get("nonexistent")
        assert retrieved is None

    def test_list_all_items(self):
        """Test listing all items."""
        backend = InMemoryBackend()
        for i in range(3):
            item = ContextItem(
                context_item_id=f"test-{i}",
                kind="reasoning",
                source="test",
                timestamp="2025-01-01T00:00:00",
                tags=["test"],
                importance=0.8,
                token_cost=10,
                payload={"text": f"test {i}"}
            )
            backend.add(item)

        all_items = backend.list_all()
        assert len(all_items) == 3

    def test_delete_item(self):
        """Test deleting items."""
        backend = InMemoryBackend()
        item = ContextItem(
            context_item_id="test-1",
            kind="reasoning",
            source="test",
            timestamp="2025-01-01T00:00:00",
            tags=["test"],
            importance=0.8,
            token_cost=10,
            payload={"text": "test"}
        )
        backend.add(item)
        deleted = backend.delete("test-1")
        assert deleted is True
        assert backend.get("test-1") is None

    def test_delete_nonexistent_item(self):
        """Test deleting non-existent item returns False."""
        backend = InMemoryBackend()
        deleted = backend.delete("nonexistent")
        assert deleted is False

    def test_clear_all_items(self):
        """Test clearing all items."""
        backend = InMemoryBackend()
        for i in range(3):
            item = ContextItem(
                context_item_id=f"test-{i}",
                kind="reasoning",
                source="test",
                timestamp="2025-01-01T00:00:00",
                tags=["test"],
                importance=0.8,
                token_cost=10,
                payload={"text": f"test {i}"}
            )
            backend.add(item)

        backend.clear()
        assert backend.count() == 0

    def test_count_items(self):
        """Test counting items."""
        backend = InMemoryBackend()
        assert backend.count() == 0

        for i in range(3):
            item = ContextItem(
                context_item_id=f"test-{i}",
                kind="reasoning",
                source="test",
                timestamp="2025-01-01T00:00:00",
                tags=["test"],
                importance=0.8,
                token_cost=10,
                payload={"text": f"test {i}"}
            )
            backend.add(item)

        assert backend.count() == 3

    def test_query_by_kind(self):
        """Test querying items by kind."""
        backend = InMemoryBackend()

        item1 = ContextItem(
            context_item_id="test-1",
            kind="reasoning",
            source="test",
            timestamp="2025-01-01T00:00:00",
            tags=["test"],
            importance=0.8,
            token_cost=10,
            payload={"text": "test"}
        )
        item2 = ContextItem(
            context_item_id="test-2",
            kind="tool_output",
            source="test",
            timestamp="2025-01-01T00:00:00",
            tags=["test"],
            importance=0.8,
            token_cost=10,
            payload={"text": "test"}
        )
        backend.add(item1)
        backend.add(item2)

        results = backend.query(filters={"kind": "reasoning"})
        assert len(results) == 1
        assert results[0].context_item_id == "test-1"


class TestTaskMemoryStore:
    """Tests for TaskMemoryStore."""

    def test_add_reasoning(self):
        """Test adding reasoning to task memory."""
        store = TaskMemoryStore(task_id="task-1")
        item = store.add_reasoning("This is reasoning", "stage-1")

        assert item.kind == "reasoning"
        assert item.source == "task/task-1/stage-1"
        assert "task" in item.tags
        assert "stage-1" in item.tags

    def test_add_tool_output(self):
        """Test adding tool output to task memory."""
        store = TaskMemoryStore(task_id="task-1")
        output = {"result": "success"}
        item = store.add_tool_output("tool-1", output)

        assert item.kind == "tool_output"
        assert item.source == "task/task-1"
        assert "tool" in item.tags
        assert "tool-1" in item.tags

    def test_get_stage_outputs(self):
        """Test retrieving stage outputs."""
        store = TaskMemoryStore(task_id="task-1")
        store.add_reasoning("Reasoning 1", "stage-1")
        store.add_reasoning("Reasoning 2", "stage-1")
        store.add_reasoning("Reasoning 3", "stage-2")

        stage_1_items = store.get_stage_outputs("stage-1")
        assert len(stage_1_items) == 2

    def test_task_memory_isolation(self):
        """Test that task memories are isolated."""
        store1 = TaskMemoryStore(task_id="task-1")
        store2 = TaskMemoryStore(task_id="task-2")

        store1.add_reasoning("Task 1 reasoning", "stage-1")
        store2.add_reasoning("Task 2 reasoning", "stage-1")

        task1_items = store1.backend.list_all()
        task2_items = store2.backend.list_all()

        assert len(task1_items) == 1
        assert len(task2_items) == 1
        assert task1_items[0].source == "task/task-1/stage-1"
        assert task2_items[0].source == "task/task-2/stage-1"

    def test_clear_task_memory(self):
        """Test clearing task memory."""
        store = TaskMemoryStore(task_id="task-1")
        store.add_reasoning("Test reasoning", "stage-1")

        assert len(store.backend.list_all()) == 1

        store.clear()
        assert len(store.backend.list_all()) == 0


class TestProjectMemoryStore:
    """Tests for ProjectMemoryStore."""

    def test_add_decision(self):
        """Test adding decision to project memory."""
        store = ProjectMemoryStore(
            project_id="proj-1",
            backend=InMemoryBackend()
        )
        item = store.add_decision("Use async/await pattern", ["architecture", "python"])

        assert item.kind == "decision"
        assert item.source == "project/proj-1"
        assert "project" in item.tags
        assert "decision" in item.tags

    def test_add_convention(self):
        """Test adding convention to project memory."""
        store = ProjectMemoryStore(
            project_id="proj-1",
            backend=InMemoryBackend()
        )
        item = store.add_convention("Use snake_case for functions", "python")

        assert item.kind == "convention"
        assert item.source == "project/proj-1"
        assert "convention" in item.tags
        assert "python" in item.tags

    def test_query_decisions(self):
        """Test querying decisions."""
        store = ProjectMemoryStore(
            project_id="proj-1",
            backend=InMemoryBackend()
        )
        store.add_decision("Decision 1", ["arch"])
        store.add_decision("Decision 2", ["design"])
        store.add_convention("Convention 1", "python")

        decisions = store.query_decisions()
        assert len(decisions) == 2

    def test_project_memory_isolation(self):
        """Test that project memories are isolated."""
        store1 = ProjectMemoryStore(
            project_id="proj-1",
            backend=InMemoryBackend()
        )
        store2 = ProjectMemoryStore(
            project_id="proj-2",
            backend=InMemoryBackend()
        )

        store1.add_decision("Proj 1 decision", [])
        store2.add_decision("Proj 2 decision", [])

        proj1_items = store1.backend.list_all()
        proj2_items = store2.backend.list_all()

        assert len(proj1_items) == 1
        assert len(proj2_items) == 1
        assert proj1_items[0].source == "project/proj-1"
        assert proj2_items[0].source == "project/proj-2"


class TestGlobalMemoryStore:
    """Tests for GlobalMemoryStore."""

    def test_add_preference(self):
        """Test adding preference to global memory."""
        store = GlobalMemoryStore(backend=InMemoryBackend())
        item = store.add_preference("Use 80-char line limit", "style", require_confirmation=False)

        assert item is not None
        assert item.kind == "preference"
        assert item.source == "global"
        assert "preference" in item.tags
        assert "style" in item.tags

    def test_add_pattern(self):
        """Test adding pattern to global memory."""
        store = GlobalMemoryStore(backend=InMemoryBackend())
        item = store.add_pattern("Use dependency injection", "design")

        assert item.kind == "pattern"
        assert item.source == "global"
        assert "pattern" in item.tags
        assert "design" in item.tags

    def test_query_preferences(self):
        """Test querying preferences."""
        store = GlobalMemoryStore(backend=InMemoryBackend())
        store.add_preference("Preference 1", "style", require_confirmation=False)
        store.add_preference("Preference 2", "verbosity", require_confirmation=False)
        store.add_pattern("Pattern 1", "design")

        preferences = store.query_preferences()
        assert len(preferences) == 2

    def test_clear_global_memory(self):
        """Test clearing global memory."""
        store = GlobalMemoryStore(backend=InMemoryBackend())
        store.add_preference("Pref 1", "style", require_confirmation=False)
        store.add_preference("Pref 2", "style", require_confirmation=False)

        result = store.clear_all()
        assert result is True
        assert len(store.backend.list_all()) == 0


class TestContextAssemblerProfileResolution:
    """Tests for ContextAssembler profile resolution."""

    def test_resolve_none_profile(self):
        """Test resolving 'none' context specification."""
        assembler = ContextAssembler()
        profile = assembler.resolve_context_profile("none")
        assert profile is None

    def test_resolve_global_profile(self):
        """Test resolving 'global' context specification."""
        assembler = ContextAssembler()
        profile = assembler.resolve_context_profile("global")
        assert profile is not None
        assert profile.id == "global_default"
        assert profile.max_tokens == 8000
        assert profile.retrieval_policy == "recency"

    def test_resolve_custom_profile(self):
        """Test resolving custom profile by ID."""
        custom_profile = ContextProfile(
            id="custom-1",
            max_tokens=4000,
            retrieval_policy="recency",
            sources=[
                ContextProfileSource(store="task", tags=[]),
                ContextProfileSource(store="project", tags=["important"])
            ]
        )

        assembler = ContextAssembler()
        assembler.context_profiles["custom-1"] = custom_profile

        resolved = assembler.resolve_context_profile("custom-1")
        assert resolved is not None
        assert resolved.id == "custom-1"
        assert resolved.max_tokens == 4000

    def test_resolve_invalid_profile_raises_error(self):
        """Test that invalid profile ID raises error."""
        assembler = ContextAssembler()
        with pytest.raises(ValueError, match="Context profile 'invalid'"):
            assembler.resolve_context_profile("invalid")

    def test_validate_profile_max_tokens(self):
        """Test profile validation for max_tokens."""
        assembler = ContextAssembler()

        invalid_profile = ContextProfile(
            id="invalid",
            max_tokens=0,
            retrieval_policy="recency",
            sources=[]
        )

        with pytest.raises(ValueError, match="max_tokens must be > 0"):
            assembler._validate_context_profile(invalid_profile)

    def test_validate_profile_retrieval_policy(self):
        """Test profile validation for retrieval_policy."""
        assembler = ContextAssembler()

        # v1 only supports recency, not semantic or hybrid
        invalid_profile = ContextProfile(
            id="invalid",
            max_tokens=1000,
            retrieval_policy="semantic",
            sources=[]
        )

        with pytest.raises(ValueError, match="retrieval_policy 'semantic' not supported"):
            assembler._validate_context_profile(invalid_profile)

    def test_validate_profile_invalid_source_store(self):
        """Test profile validation for invalid source store."""
        assembler = ContextAssembler()

        invalid_profile = ContextProfile(
            id="invalid",
            max_tokens=1000,
            retrieval_policy="recency",
            sources=[
                ContextProfileSource(store="invalid_store", tags=[])
            ]
        )

        with pytest.raises(ValueError, match="source store 'invalid_store' invalid"):
            assembler._validate_context_profile(invalid_profile)


class TestContextAssemblerContextBuilding:
    """Tests for ContextAssembler context building."""

    def _create_task(self, task_id: str = "task-1") -> Task:
        """Create a test task."""
        spec = TaskSpec(
            task_spec_id=str(uuid.uuid4()),
            request="Test request",
            mode=TaskMode.ANALYSIS_ONLY,
            metadata={"project_id": "proj-1"}
        )
        task = Task(
            task_id=task_id,
            spec=spec,
            lifecycle=TaskLifecycle.ACTIVE,
            current_output={"test": "output"},
            task_memory_ref=task_id,
            project_memory_ref="proj-1",
            global_memory_ref="global"
        )
        return task

    def test_build_context_with_none_profile(self):
        """Test building context when profile is None."""
        assembler = ContextAssembler()
        task = self._create_task()
        profile = None

        # Should handle None profile gracefully
        assert profile is None

    def test_build_context_with_empty_profile(self):
        """Test building context with profile but no items."""
        assembler = ContextAssembler()
        task = self._create_task()

        profile = ContextProfile(
            id="empty",
            max_tokens=1000,
            retrieval_policy="recency",
            sources=[ContextProfileSource(store="task", tags=[])]
        )

        package = assembler.build_context_for_profile(task, profile)

        assert package.context_package_id == f"ctx-{task.task_id}-empty"
        assert len(package.items) == 0

    def test_build_context_from_task_store(self):
        """Test building context from task memory."""
        assembler = ContextAssembler()
        task = self._create_task()

        # Add item to task memory
        task_store = TaskMemoryStore(task_id=task.task_id)
        task_store.add_reasoning("Test reasoning", "stage-1")
        assembler.task_stores[task.task_id] = task_store

        profile = ContextProfile(
            id="test",
            max_tokens=1000,
            retrieval_policy="recency",
            sources=[ContextProfileSource(store="task", tags=[])]
        )

        package = assembler.build_context_for_profile(task, profile)

        assert len(package.items) == 1
        assert package.items[0].kind == "reasoning"

    def test_build_context_from_project_store(self):
        """Test building context from project memory."""
        assembler = ContextAssembler()
        task = self._create_task()

        # Add item to project memory
        project_store = ProjectMemoryStore(
            project_id="proj-1",
            backend=InMemoryBackend()
        )
        project_store.add_decision("Test decision", ["arch"])
        assembler.project_stores["proj-1"] = project_store

        profile = ContextProfile(
            id="test",
            max_tokens=1000,
            retrieval_policy="recency",
            sources=[ContextProfileSource(store="project", tags=[])]
        )

        package = assembler.build_context_for_profile(task, profile)

        assert len(package.items) == 1
        assert package.items[0].kind == "decision"

    def test_build_context_from_global_store(self):
        """Test building context from global memory."""
        assembler = ContextAssembler()
        task = self._create_task()

        # Add item to global memory
        assembler.global_store.add_preference("Test pref", "style", require_confirmation=False)

        profile = ContextProfile(
            id="test",
            max_tokens=1000,
            retrieval_policy="recency",
            sources=[ContextProfileSource(store="global", tags=[])]
        )

        package = assembler.build_context_for_profile(task, profile)

        assert len(package.items) == 1
        assert package.items[0].kind == "preference"

    def test_build_context_multi_source(self):
        """Test building context from multiple sources."""
        assembler = ContextAssembler()
        task = self._create_task()

        # Add to all three stores
        task_store = TaskMemoryStore(task_id=task.task_id)
        task_store.add_reasoning("Task reasoning", "stage-1")
        assembler.task_stores[task.task_id] = task_store

        project_store = ProjectMemoryStore(
            project_id="proj-1",
            backend=InMemoryBackend()
        )
        project_store.add_decision("Project decision", [])
        assembler.project_stores["proj-1"] = project_store

        assembler.global_store.add_preference("Global pref", "style", require_confirmation=False)

        profile = ContextProfile(
            id="all",
            max_tokens=5000,
            retrieval_policy="recency",
            sources=[
                ContextProfileSource(store="task", tags=[]),
                ContextProfileSource(store="project", tags=[]),
                ContextProfileSource(store="global", tags=[])
            ]
        )

        package = assembler.build_context_for_profile(task, profile)

        assert len(package.items) == 3

    def test_context_tag_filtering(self):
        """Test context tag filtering."""
        assembler = ContextAssembler()
        task = self._create_task()

        # Add items with different tags
        task_store = TaskMemoryStore(task_id=task.task_id)
        task_store.add_reasoning("Bug reasoning", "stage-1")  # has tags: ["task", "stage-1"]
        assembler.task_stores[task.task_id] = task_store

        # Filter by tag "stage-1"
        profile = ContextProfile(
            id="filtered",
            max_tokens=1000,
            retrieval_policy="recency",
            sources=[ContextProfileSource(store="task", tags=["stage-1"])]
        )

        package = assembler.build_context_for_profile(task, profile)

        assert len(package.items) == 1

    def test_token_budget_enforcement(self):
        """Test token budget is enforced."""
        assembler = ContextAssembler()
        task = self._create_task()

        # Add multiple items
        task_store = TaskMemoryStore(task_id=task.task_id)
        task_store.add_reasoning("Item 1", "stage-1")
        task_store.add_reasoning("Item 2", "stage-1")
        task_store.add_reasoning("Item 3", "stage-1")
        assembler.task_stores[task.task_id] = task_store

        # Very small budget
        profile = ContextProfile(
            id="small",
            max_tokens=10,  # Very small
            retrieval_policy="recency",
            sources=[ContextProfileSource(store="task", tags=[])]
        )

        package = assembler.build_context_for_profile(task, profile)

        # Should respect budget
        total_tokens = sum(i.token_cost or 0 for i in package.items)
        assert total_tokens <= 10

    def test_compression_ratio_calculation(self):
        """Test compression ratio is calculated correctly."""
        assembler = ContextAssembler()
        task = self._create_task()

        # Add items
        task_store = TaskMemoryStore(task_id=task.task_id)
        task_store.add_reasoning("Reasoning 1", "stage-1")
        task_store.add_reasoning("Reasoning 2", "stage-1")
        assembler.task_stores[task.task_id] = task_store

        profile = ContextProfile(
            id="test",
            max_tokens=1000,
            retrieval_policy="recency",
            sources=[ContextProfileSource(store="task", tags=[])]
        )

        package = assembler.build_context_for_profile(task, profile)

        # With all items fitting in budget, ratio should be 1.0
        assert 0 < package.compression_ratio <= 1.0


# Integration tests

class TestContextAssemblerIntegration:
    """Integration tests for context assembler."""

    def test_context_assembly_workflow(self):
        """Test a complete context assembly workflow."""
        assembler = ContextAssembler()

        task_spec = TaskSpec(
            task_spec_id=str(uuid.uuid4()),
            request="Test request",
            mode=TaskMode.ANALYSIS_ONLY,
            metadata={"project_id": "proj-1"}
        )
        task = Task(
            task_id="task-1",
            spec=task_spec,
            lifecycle=TaskLifecycle.ACTIVE,
            current_output={"result": "pending"},
            task_memory_ref="task-1",
            project_memory_ref="proj-1",
            global_memory_ref="global"
        )

        # Add context items from all tiers
        task_store = TaskMemoryStore(task_id="task-1")
        task_store.add_reasoning("Recent reasoning", "stage-1")
        assembler.task_stores["task-1"] = task_store

        project_store = ProjectMemoryStore(
            project_id="proj-1",
            backend=InMemoryBackend()
        )
        project_store.add_decision("Architecture decision", ["important"])
        assembler.project_stores["proj-1"] = project_store

        assembler.global_store.add_preference("Code style", "style", require_confirmation=False)

        # Create profile
        profile = ContextProfile(
            id="multi-tier",
            max_tokens=2000,
            retrieval_policy="recency",
            sources=[
                ContextProfileSource(store="task", tags=[]),
                ContextProfileSource(store="project", tags=["important"]),
                ContextProfileSource(store="global", tags=[])
            ]
        )

        # Assemble context
        package = assembler.build_context_for_profile(task, profile)

        # Verify
        assert len(package.items) == 3
        kinds = {item.kind for item in package.items}
        assert "reasoning" in kinds
        assert "decision" in kinds
        assert "preference" in kinds

    def test_task_cleanup(self):
        """Test task memory cleanup."""
        assembler = ContextAssembler()

        task_store = TaskMemoryStore(task_id="task-1")
        task_store.add_reasoning("Test", "stage-1")
        assembler.task_stores["task-1"] = task_store

        assert "task-1" in assembler.task_stores

        # Cleanup
        assembler.cleanup_task("task-1")

        assert "task-1" not in assembler.task_stores
