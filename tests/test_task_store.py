"""Tests for TaskMemoryStore."""

import pytest
from agent_engine.runtime.memory import TaskMemoryStore
from agent_engine.runtime.memory.backend import InMemoryBackend
from agent_engine.schemas import ContextItem


class TestTaskMemoryStore:
    """Test suite for TaskMemoryStore class."""

    @pytest.fixture
    def task_store(self):
        """Create a fresh TaskMemoryStore for each test."""
        return TaskMemoryStore(task_id="test-task-123")

    def test_add_reasoning_creates_context_item(self, task_store):
        """Test that add_reasoning creates a ContextItem with correct structure."""
        text = "This is reasoning about the problem"
        stage_id = "analysis_stage"

        result = task_store.add_reasoning(text, stage_id)

        assert isinstance(result, ContextItem)
        assert result.kind == "reasoning"
        assert result.source == "task/test-task-123/analysis_stage"
        assert "task" in result.tags
        assert stage_id in result.tags
        assert result.importance == 0.5
        assert result.payload["text"] == text
        assert result.context_item_id.startswith("reasoning-analysis_stage-")

    def test_add_tool_output_creates_context_item(self, task_store):
        """Test that add_tool_output creates a ContextItem with correct structure."""
        tool_id = "search_tool"
        output = {"results": ["item1", "item2"], "count": 2}

        result = task_store.add_tool_output(tool_id, output)

        assert isinstance(result, ContextItem)
        assert result.kind == "tool_output"
        assert result.source == "task/test-task-123"
        assert "task" in result.tags
        assert "tool" in result.tags
        assert tool_id in result.tags
        assert result.importance == 0.7
        assert result.payload["tool_id"] == tool_id
        assert result.payload["output"] == output
        assert result.context_item_id.startswith("tool-search_tool-")

    def test_add_reasoning_stores_in_backend(self, task_store):
        """Test that add_reasoning actually stores item in backend."""
        text = "Test reasoning"
        stage_id = "stage1"

        result = task_store.add_reasoning(text, stage_id)

        # Verify it was stored by retrieving it
        stored_item = task_store.backend.get(result.context_item_id)
        assert stored_item is not None
        assert stored_item.kind == "reasoning"
        assert stored_item.payload["text"] == text

    def test_add_tool_output_stores_in_backend(self, task_store):
        """Test that add_tool_output actually stores item in backend."""
        tool_id = "my_tool"
        output = "Tool output result"

        result = task_store.add_tool_output(tool_id, output)

        # Verify it was stored
        stored_item = task_store.backend.get(result.context_item_id)
        assert stored_item is not None
        assert stored_item.kind == "tool_output"
        assert stored_item.payload["tool_id"] == tool_id
        assert stored_item.payload["output"] == output

    def test_get_stage_outputs_filters_correctly(self, task_store):
        """Test that get_stage_outputs returns only items from the specified stage."""
        # Add reasoning for stage 1
        reasoning1a = task_store.add_reasoning("Reasoning 1a", "stage1")
        reasoning1b = task_store.add_reasoning("Reasoning 1b", "stage1")

        # Add reasoning for stage 2
        reasoning2a = task_store.add_reasoning("Reasoning 2a", "stage2")

        # Add tool output (no stage)
        tool_out = task_store.add_tool_output("tool1", "output")

        # Query stage 1
        stage1_items = task_store.get_stage_outputs("stage1")

        assert len(stage1_items) == 2
        assert all(item.source == "task/test-task-123/stage1" for item in stage1_items)
        # Verify the exact items
        stage1_ids = {item.context_item_id for item in stage1_items}
        assert reasoning1a.context_item_id in stage1_ids
        assert reasoning1b.context_item_id in stage1_ids

    def test_get_stage_outputs_empty_stage(self, task_store):
        """Test get_stage_outputs returns empty list for stage with no items."""
        # Add some items for a different stage
        task_store.add_reasoning("Something", "stage1")

        # Query empty stage
        result = task_store.get_stage_outputs("stage_empty")

        assert isinstance(result, list)
        assert len(result) == 0

    def test_get_stage_outputs_does_not_include_tool_outputs(self, task_store):
        """Test that get_stage_outputs doesn't return tool outputs (different source)."""
        # Add reasoning for a stage
        reasoning = task_store.add_reasoning("Stage reasoning", "stage1")

        # Add tool output
        task_store.add_tool_output("tool1", "output")

        # Query stage
        stage_items = task_store.get_stage_outputs("stage1")

        # Should only have the reasoning
        assert len(stage_items) == 1
        assert stage_items[0].kind == "reasoning"

    def test_clear_removes_all_items(self, task_store):
        """Test that clear() removes all stored items."""
        # Add multiple items
        task_store.add_reasoning("Text 1", "stage1")
        task_store.add_reasoning("Text 2", "stage1")
        task_store.add_tool_output("tool1", "output1")
        task_store.add_tool_output("tool2", "output2")

        # Verify items were stored
        assert task_store.backend.count() == 4

        # Clear
        task_store.clear()

        # Verify all items removed
        assert task_store.backend.count() == 0
        assert len(task_store.backend.list_all()) == 0

    def test_clear_allows_reuse(self, task_store):
        """Test that store can be reused after clearing."""
        # Add and clear
        task_store.add_reasoning("Text", "stage1")
        task_store.clear()

        # Add again
        new_item = task_store.add_reasoning("New text", "stage1")

        # Should work normally
        assert task_store.backend.count() == 1
        assert task_store.backend.get(new_item.context_item_id) is not None

    def test_multiple_stages_dont_interfere(self, task_store):
        """Test that multiple stages maintain separate outputs."""
        # Add items for different stages
        stage1_items = [
            task_store.add_reasoning(f"Stage 1 reasoning {i}", "stage1")
            for i in range(3)
        ]
        stage2_items = [
            task_store.add_reasoning(f"Stage 2 reasoning {i}", "stage2")
            for i in range(2)
        ]
        stage3_items = [
            task_store.add_reasoning(f"Stage 3 reasoning {i}", "stage3")
            for i in range(4)
        ]

        # Verify total count
        assert task_store.backend.count() == 9

        # Verify each stage returns only its items
        s1 = task_store.get_stage_outputs("stage1")
        s2 = task_store.get_stage_outputs("stage2")
        s3 = task_store.get_stage_outputs("stage3")

        assert len(s1) == 3
        assert len(s2) == 2
        assert len(s3) == 4

        # Verify no overlap
        s1_ids = {item.context_item_id for item in s1}
        s2_ids = {item.context_item_id for item in s2}
        s3_ids = {item.context_item_id for item in s3}

        assert s1_ids.isdisjoint(s2_ids)
        assert s1_ids.isdisjoint(s3_ids)
        assert s2_ids.isdisjoint(s3_ids)

    def test_token_cost_calculated_for_reasoning(self, task_store):
        """Test that token_cost is calculated correctly for reasoning."""
        text = "This is a test sentence with multiple words in it"
        result = task_store.add_reasoning(text, "stage1")

        # Count words
        word_count = len(text.split())
        assert result.token_cost == word_count

    def test_token_cost_calculated_for_tool_output(self, task_store):
        """Test that token_cost is calculated correctly for tool output."""
        output = {"key": "value", "list": [1, 2, 3]}
        result = task_store.add_tool_output("tool1", output)

        # Token cost should be calculated from string representation
        expected_tokens = len(str(output).split())
        assert result.token_cost == expected_tokens

    def test_timestamp_is_set(self, task_store):
        """Test that timestamp is set in ISO format."""
        result = task_store.add_reasoning("Text", "stage1")

        assert result.timestamp is not None
        # Check it's a valid ISO format string
        from datetime import datetime
        datetime.fromisoformat(result.timestamp)  # Should not raise

    def test_different_task_stores_isolated(self):
        """Test that different TaskMemoryStore instances are isolated."""
        store1 = TaskMemoryStore(task_id="task1")
        store2 = TaskMemoryStore(task_id="task2")

        # Add items to each store
        item1 = store1.add_reasoning("Task 1 reasoning", "stage1")
        item2 = store2.add_reasoning("Task 2 reasoning", "stage1")

        # Each store should only have its item
        assert store1.backend.count() == 1
        assert store2.backend.count() == 1

        # Verify isolation
        assert store1.backend.get(item1.context_item_id) is not None
        assert store1.backend.get(item2.context_item_id) is None

        assert store2.backend.get(item2.context_item_id) is not None
        assert store2.backend.get(item1.context_item_id) is None

    def test_source_includes_task_id(self, task_store):
        """Test that source field always includes task_id."""
        reasoning = task_store.add_reasoning("Text", "stage1")
        tool_output = task_store.add_tool_output("tool1", "output")

        assert "test-task-123" in reasoning.source
        assert "test-task-123" in tool_output.source
        assert reasoning.source.startswith("task/test-task-123")
        assert tool_output.source.startswith("task/test-task-123")

    def test_reasoning_context_item_id_format(self, task_store):
        """Test that reasoning context_item_id follows expected format."""
        result = task_store.add_reasoning("Text", "stage1")

        # Should start with reasoning- prefix
        assert result.context_item_id.startswith("reasoning-")
        # Should have stage_id after prefix
        assert "-stage1-" in result.context_item_id
        # Should contain UUID part (after stage_id)
        parts = result.context_item_id.split("-")
        assert len(parts) >= 3  # reasoning, stage1, uuid parts

    def test_tool_output_context_item_id_format(self, task_store):
        """Test that tool_output context_item_id follows expected format."""
        result = task_store.add_tool_output("search_tool", "output")

        # Should start with tool- prefix
        assert result.context_item_id.startswith("tool-")
        # Should have tool_id after prefix
        assert "-search_tool-" in result.context_item_id
        # Should contain UUID part
        parts = result.context_item_id.split("-")
        assert len(parts) >= 3

    def test_uses_custom_backend_if_provided(self):
        """Test that TaskMemoryStore uses provided backend."""
        custom_backend = InMemoryBackend()
        store = TaskMemoryStore(task_id="task1", backend=custom_backend)

        # Add item
        result = store.add_reasoning("Text", "stage1")

        # Verify it's in the custom backend
        assert custom_backend.count() == 1
        assert custom_backend.get(result.context_item_id) is not None
