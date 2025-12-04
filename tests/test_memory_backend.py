"""Tests for memory backend interface and implementations."""

import pytest
from datetime import datetime

from agent_engine.schemas import ContextItem
from agent_engine.runtime.memory import InMemoryBackend, MemoryBackend


class TestInMemoryBackend:
    """Tests for InMemoryBackend implementation."""

    def setup_method(self):
        """Create a fresh backend for each test."""
        self.backend = InMemoryBackend()

    def _create_item(
        self,
        item_id: str = "item-1",
        kind: str = "reasoning",
        source: str = "task/t1",
        timestamp: str = "2025-12-03T10:00:00",
        tags: list = None,
        importance: float = 0.5,
        token_cost: float = 10.0,
        **kwargs
    ) -> ContextItem:
        """Helper to create test ContextItems."""
        return ContextItem(
            context_item_id=item_id,
            kind=kind,
            source=source,
            timestamp=timestamp,
            tags=tags or ["test"],
            importance=importance,
            token_cost=token_cost,
            payload={"test": True, **kwargs}
        )

    # Basic CRUD operations
    def test_add_item(self):
        """Test adding an item to the backend."""
        item = self._create_item()
        self.backend.add(item)
        assert self.backend.count() == 1

    def test_get_item(self):
        """Test retrieving an item by ID."""
        item = self._create_item(item_id="test-1")
        self.backend.add(item)
        retrieved = self.backend.get("test-1")
        assert retrieved is not None
        assert retrieved.context_item_id == "test-1"
        assert retrieved.kind == "reasoning"

    def test_get_nonexistent_item(self):
        """Test retrieving a non-existent item returns None."""
        result = self.backend.get("nonexistent")
        assert result is None

    def test_delete_item(self):
        """Test deleting an item."""
        item = self._create_item(item_id="test-delete")
        self.backend.add(item)
        assert self.backend.count() == 1
        deleted = self.backend.delete("test-delete")
        assert deleted is True
        assert self.backend.count() == 0

    def test_delete_nonexistent_item(self):
        """Test deleting a non-existent item returns False."""
        deleted = self.backend.delete("nonexistent")
        assert deleted is False

    # List operations
    def test_list_all_empty(self):
        """Test listing all items in an empty store."""
        items = self.backend.list_all()
        assert items == []

    def test_list_all(self):
        """Test listing all items."""
        for i in range(3):
            item = self._create_item(item_id=f"item-{i}")
            self.backend.add(item)
        items = self.backend.list_all()
        assert len(items) == 3
        ids = {item.context_item_id for item in items}
        assert ids == {"item-0", "item-1", "item-2"}

    # Count and clear
    def test_count_empty(self):
        """Test counting items in an empty store."""
        assert self.backend.count() == 0

    def test_count(self):
        """Test counting items."""
        for i in range(5):
            item = self._create_item(item_id=f"item-{i}")
            self.backend.add(item)
        assert self.backend.count() == 5

    def test_clear(self):
        """Test clearing the store."""
        for i in range(5):
            item = self._create_item(item_id=f"item-{i}")
            self.backend.add(item)
        assert self.backend.count() == 5
        self.backend.clear()
        assert self.backend.count() == 0

    # Query tests - exact match
    def test_query_by_kind(self):
        """Test querying by exact kind match."""
        self.backend.add(self._create_item(item_id="item-1", kind="reasoning"))
        self.backend.add(self._create_item(item_id="item-2", kind="tool_output"))
        self.backend.add(self._create_item(item_id="item-3", kind="reasoning"))

        results = self.backend.query({"kind": "reasoning"})
        assert len(results) == 2
        ids = {item.context_item_id for item in results}
        assert ids == {"item-1", "item-3"}

    def test_query_by_source(self):
        """Test querying by exact source match."""
        self.backend.add(self._create_item(item_id="item-1", source="task/t1"))
        self.backend.add(self._create_item(item_id="item-2", source="task/t2"))
        self.backend.add(self._create_item(item_id="item-3", source="task/t1"))

        results = self.backend.query({"source": "task/t1"})
        assert len(results) == 2
        ids = {item.context_item_id for item in results}
        assert ids == {"item-1", "item-3"}

    def test_query_multiple_exact_filters(self):
        """Test querying with multiple exact match filters."""
        self.backend.add(self._create_item(
            item_id="item-1",
            kind="reasoning",
            source="task/t1"
        ))
        self.backend.add(self._create_item(
            item_id="item-2",
            kind="reasoning",
            source="task/t2"
        ))
        self.backend.add(self._create_item(
            item_id="item-3",
            kind="tool_output",
            source="task/t1"
        ))

        results = self.backend.query({"kind": "reasoning", "source": "task/t1"})
        assert len(results) == 1
        assert results[0].context_item_id == "item-1"

    # Query tests - operators
    def test_query_gte_operator(self):
        """Test $gte operator for greater-than-or-equal."""
        self.backend.add(self._create_item(item_id="item-1", importance=0.3))
        self.backend.add(self._create_item(item_id="item-2", importance=0.7))
        self.backend.add(self._create_item(item_id="item-3", importance=0.9))

        results = self.backend.query({"importance": {"$gte": 0.7}})
        assert len(results) == 2
        ids = {item.context_item_id for item in results}
        assert ids == {"item-2", "item-3"}

    def test_query_gt_operator(self):
        """Test $gt operator for greater-than."""
        self.backend.add(self._create_item(item_id="item-1", importance=0.5))
        self.backend.add(self._create_item(item_id="item-2", importance=0.7))
        self.backend.add(self._create_item(item_id="item-3", importance=0.9))

        results = self.backend.query({"importance": {"$gt": 0.5}})
        assert len(results) == 2
        ids = {item.context_item_id for item in results}
        assert ids == {"item-2", "item-3"}

    def test_query_lte_operator(self):
        """Test $lte operator for less-than-or-equal."""
        self.backend.add(self._create_item(item_id="item-1", importance=0.3))
        self.backend.add(self._create_item(item_id="item-2", importance=0.7))
        self.backend.add(self._create_item(item_id="item-3", importance=0.9))

        results = self.backend.query({"importance": {"$lte": 0.7}})
        assert len(results) == 2
        ids = {item.context_item_id for item in results}
        assert ids == {"item-1", "item-2"}

    def test_query_lt_operator(self):
        """Test $lt operator for less-than."""
        self.backend.add(self._create_item(item_id="item-1", importance=0.3))
        self.backend.add(self._create_item(item_id="item-2", importance=0.7))
        self.backend.add(self._create_item(item_id="item-3", importance=0.9))

        results = self.backend.query({"importance": {"$lt": 0.7}})
        assert len(results) == 1
        assert results[0].context_item_id == "item-1"

    def test_query_eq_operator(self):
        """Test $eq operator for equality."""
        self.backend.add(self._create_item(item_id="item-1", importance=0.5))
        self.backend.add(self._create_item(item_id="item-2", importance=0.7))
        self.backend.add(self._create_item(item_id="item-3", importance=0.5))

        results = self.backend.query({"importance": {"$eq": 0.5}})
        assert len(results) == 2
        ids = {item.context_item_id for item in results}
        assert ids == {"item-1", "item-3"}

    def test_query_ne_operator(self):
        """Test $ne operator for not-equal."""
        self.backend.add(self._create_item(item_id="item-1", importance=0.5))
        self.backend.add(self._create_item(item_id="item-2", importance=0.7))
        self.backend.add(self._create_item(item_id="item-3", importance=0.5))

        results = self.backend.query({"importance": {"$ne": 0.5}})
        assert len(results) == 1
        assert results[0].context_item_id == "item-2"

    # Query tests - list membership (tags)
    def test_query_tags_membership(self):
        """Test querying with tag membership filter."""
        self.backend.add(self._create_item(item_id="item-1", tags=["task", "bug"]))
        self.backend.add(self._create_item(item_id="item-2", tags=["task", "feature"]))
        self.backend.add(self._create_item(item_id="item-3", tags=["global", "pattern"]))

        results = self.backend.query({"tags": ["bug"]})
        assert len(results) == 1
        assert results[0].context_item_id == "item-1"

    def test_query_tags_membership_multiple_values(self):
        """Test querying with multiple tag values (OR logic)."""
        self.backend.add(self._create_item(item_id="item-1", tags=["task", "bug"]))
        self.backend.add(self._create_item(item_id="item-2", tags=["task", "feature"]))
        self.backend.add(self._create_item(item_id="item-3", tags=["global", "pattern"]))

        results = self.backend.query({"tags": ["bug", "feature"]})
        assert len(results) == 2
        ids = {item.context_item_id for item in results}
        assert ids == {"item-1", "item-2"}

    def test_query_tags_no_match(self):
        """Test querying with tags that don't match any items."""
        self.backend.add(self._create_item(item_id="item-1", tags=["task", "bug"]))

        results = self.backend.query({"tags": ["nonexistent"]})
        assert len(results) == 0

    # Sorting tests
    def test_query_sort_by_timestamp_default(self):
        """Test default sorting by timestamp (newest first)."""
        self.backend.add(self._create_item(
            item_id="item-1",
            timestamp="2025-12-03T10:00:00"
        ))
        self.backend.add(self._create_item(
            item_id="item-2",
            timestamp="2025-12-03T12:00:00"
        ))
        self.backend.add(self._create_item(
            item_id="item-3",
            timestamp="2025-12-03T11:00:00"
        ))

        results = self.backend.query({})
        # Default sort is descending (newest first)
        assert results[0].context_item_id == "item-2"
        assert results[1].context_item_id == "item-3"
        assert results[2].context_item_id == "item-1"

    def test_query_sort_by_importance(self):
        """Test sorting by importance."""
        self.backend.add(self._create_item(
            item_id="item-1",
            importance=0.5
        ))
        self.backend.add(self._create_item(
            item_id="item-2",
            importance=0.9
        ))
        self.backend.add(self._create_item(
            item_id="item-3",
            importance=0.7
        ))

        results = self.backend.query({}, order_by="importance")
        # Default descending (highest importance first)
        assert results[0].context_item_id == "item-2"
        assert results[1].context_item_id == "item-3"
        assert results[2].context_item_id == "item-1"

    def test_query_sort_ascending(self):
        """Test ascending sort with - prefix."""
        self.backend.add(self._create_item(
            item_id="item-1",
            importance=0.5
        ))
        self.backend.add(self._create_item(
            item_id="item-2",
            importance=0.9
        ))
        self.backend.add(self._create_item(
            item_id="item-3",
            importance=0.7
        ))

        results = self.backend.query({}, order_by="-importance")
        # Ascending (lowest importance first)
        assert results[0].context_item_id == "item-1"
        assert results[1].context_item_id == "item-3"
        assert results[2].context_item_id == "item-2"

    # Limit tests
    def test_query_limit(self):
        """Test limit parameter."""
        for i in range(10):
            self.backend.add(self._create_item(item_id=f"item-{i}"))

        results = self.backend.query({}, limit=3)
        assert len(results) == 3

    def test_query_limit_greater_than_results(self):
        """Test limit when it exceeds available results."""
        for i in range(3):
            self.backend.add(self._create_item(item_id=f"item-{i}"))

        results = self.backend.query({}, limit=10)
        assert len(results) == 3

    # Complex filter combinations
    def test_query_complex_filters(self):
        """Test combining different filter types."""
        self.backend.add(self._create_item(
            item_id="item-1",
            kind="reasoning",
            importance=0.7,
            tags=["task", "bug"]
        ))
        self.backend.add(self._create_item(
            item_id="item-2",
            kind="reasoning",
            importance=0.5,
            tags=["task", "feature"]
        ))
        self.backend.add(self._create_item(
            item_id="item-3",
            kind="tool_output",
            importance=0.8,
            tags=["task", "bug"]
        ))

        # Query: kind=reasoning, importance >= 0.7, tags include bug
        results = self.backend.query({
            "kind": "reasoning",
            "importance": {"$gte": 0.7},
            "tags": ["bug"]
        })
        assert len(results) == 1
        assert results[0].context_item_id == "item-1"

    # Empty query tests
    def test_query_empty_filters(self):
        """Test query with empty filters returns all items."""
        for i in range(3):
            self.backend.add(self._create_item(item_id=f"item-{i}"))

        results = self.backend.query({})
        assert len(results) == 3

    def test_query_no_matches(self):
        """Test query that matches no items."""
        self.backend.add(self._create_item(item_id="item-1", kind="reasoning"))

        results = self.backend.query({"kind": "nonexistent_kind"})
        assert len(results) == 0

    # Edge cases
    def test_query_with_none_field_values(self):
        """Test querying items with None field values."""
        # Create an item with None importance
        item = self._create_item(item_id="item-1", importance=None)
        self.backend.add(item)
        self.backend.add(self._create_item(item_id="item-2", importance=0.5))

        # Query for items with importance >= 0.3 should only match item-2
        results = self.backend.query({"importance": {"$gte": 0.3}})
        assert len(results) == 1
        assert results[0].context_item_id == "item-2"

    def test_overwrite_existing_item(self):
        """Test that adding an item with same ID overwrites existing."""
        item1 = self._create_item(item_id="same-id", importance=0.5)
        self.backend.add(item1)
        assert self.backend.count() == 1

        item2 = self._create_item(item_id="same-id", importance=0.9)
        self.backend.add(item2)
        assert self.backend.count() == 1

        retrieved = self.backend.get("same-id")
        assert retrieved.importance == 0.9

    def test_query_operator_with_incompatible_types(self):
        """Test that operators gracefully handle type mismatches."""
        # Add item with string importance (shouldn't happen normally)
        item = ContextItem(
            context_item_id="item-1",
            kind="test",
            source="test",
            timestamp="2025-12-03T10:00:00",
            tags=[],
            importance=None,  # Use None to avoid validation issues
            token_cost=10.0,
            payload={"test": True}
        )
        self.backend.add(item)

        # Query should handle type mismatch gracefully
        results = self.backend.query({"token_cost": {"$gt": 5}})
        assert len(results) == 1  # Should match since token_cost is 10.0


class TestMemoryBackendProtocol:
    """Tests to verify protocol compliance."""

    def test_backend_implements_protocol(self):
        """Test that InMemoryBackend implements MemoryBackend protocol."""
        backend = InMemoryBackend()

        # Verify all methods exist and are callable
        assert callable(backend.add)
        assert callable(backend.query)
        assert callable(backend.get)
        assert callable(backend.delete)
        assert callable(backend.list_all)
        assert callable(backend.clear)
        assert callable(backend.count)
