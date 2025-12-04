"""Tests for GlobalMemoryStore."""

import pytest
from unittest.mock import Mock

from agent_engine.runtime.memory.backend import InMemoryBackend
from agent_engine.runtime.memory.global_store import GlobalMemoryStore
from agent_engine.schemas.memory import ContextItem


class TestGlobalMemoryStore:
    """Test suite for GlobalMemoryStore."""

    @pytest.fixture
    def backend(self):
        """Provide a fresh backend for each test."""
        return InMemoryBackend()

    @pytest.fixture
    def store(self, backend):
        """Provide a store without confirmation callback."""
        return GlobalMemoryStore(backend=backend)

    @pytest.fixture
    def store_with_callback(self, backend):
        """Provide a store with a confirmation callback."""
        callback = Mock(return_value=True)
        return GlobalMemoryStore(backend=backend, confirmation_callback=callback)

    # Tests for add_preference

    def test_add_preference_without_confirmation(self, store):
        """Test adding a preference without requiring confirmation."""
        item = store.add_preference(
            preference="Use type hints everywhere",
            category="style"
        )

        assert item is not None
        assert item.kind == "preference"
        assert item.source == "global"
        assert "preference" in item.tags
        assert "style" in item.tags
        assert "global" in item.tags
        assert item.importance == 0.9
        assert item.payload["preference"] == "Use type hints everywhere"
        assert item.payload["category"] == "style"

    def test_add_preference_with_confirmation_approved(self, store_with_callback):
        """Test adding a preference with confirmation when user approves."""
        callback = store_with_callback.confirmation_callback
        callback.return_value = True

        item = store_with_callback.add_preference(
            preference="Always document APIs",
            category="documentation",
            require_confirmation=True
        )

        assert item is not None
        assert item.kind == "preference"
        callback.assert_called_once()
        assert "Always document APIs" in callback.call_args[0][0]
        assert "documentation" in callback.call_args[0][0]

    def test_add_preference_with_confirmation_denied(self, store_with_callback):
        """Test adding a preference with confirmation when user declines."""
        callback = store_with_callback.confirmation_callback
        callback.return_value = False

        item = store_with_callback.add_preference(
            preference="Use async everywhere",
            category="concurrency",
            require_confirmation=True
        )

        assert item is None
        callback.assert_called_once()

    def test_add_preference_no_callback_no_confirmation_required(self, store):
        """Test that no confirmation is requested when not required."""
        # Store has no callback
        item = store.add_preference(
            preference="Test preference",
            category="test",
            require_confirmation=False
        )

        assert item is not None
        assert item.kind == "preference"

    def test_add_preference_no_callback_with_confirmation_required(self, store):
        """Test that preference is added when confirmation required but no callback."""
        # No callback, so confirmation_callback is None
        # Should skip confirmation and add anyway
        item = store.add_preference(
            preference="Require confirmation but no callback",
            category="test",
            require_confirmation=True
        )

        assert item is not None
        assert item.kind == "preference"

    def test_add_preference_token_cost(self, store):
        """Test that token cost is calculated correctly."""
        preference_text = "Use type hints everywhere in the codebase"
        item = store.add_preference(
            preference=preference_text,
            category="style"
        )

        expected_tokens = len(preference_text.split())
        assert item.token_cost == expected_tokens

    # Tests for add_pattern

    def test_add_pattern(self, store):
        """Test adding a reusable pattern."""
        item = store.add_pattern(
            pattern="Always write tests alongside code",
            domain="testing"
        )

        assert item is not None
        assert item.kind == "pattern"
        assert item.source == "global"
        assert "pattern" in item.tags
        assert "testing" in item.tags
        assert "global" in item.tags
        assert item.importance == 0.7
        assert item.payload["pattern"] == "Always write tests alongside code"
        assert item.payload["domain"] == "testing"

    def test_add_pattern_token_cost(self, store):
        """Test that token cost is calculated correctly for patterns."""
        pattern_text = "Use defensive programming with input validation"
        item = store.add_pattern(pattern=pattern_text, domain="security")

        expected_tokens = len(pattern_text.split())
        assert item.token_cost == expected_tokens

    def test_add_multiple_patterns(self, store):
        """Test adding multiple patterns."""
        pattern1 = store.add_pattern("Pattern 1", "domain1")
        pattern2 = store.add_pattern("Pattern 2", "domain2")

        assert pattern1.context_item_id != pattern2.context_item_id
        assert pattern1.payload["domain"] == "domain1"
        assert pattern2.payload["domain"] == "domain2"

    # Tests for query_preferences

    def test_query_preferences_empty(self, store):
        """Test querying preferences from empty store."""
        results = store.query_preferences()
        assert results == []

    def test_query_preferences_all(self, store):
        """Test querying all preferences."""
        pref1 = store.add_preference("Pref 1", "style")
        pref2 = store.add_preference("Pref 2", "verbosity")

        results = store.query_preferences()

        assert len(results) == 2
        ids = {r.context_item_id for r in results}
        assert pref1.context_item_id in ids
        assert pref2.context_item_id in ids

    def test_query_preferences_by_category(self, store):
        """Test querying preferences filtered by category."""
        style_pref = store.add_preference("Use type hints", "style")
        verb_pref = store.add_preference("Be verbose", "verbosity")
        another_style = store.add_preference("Use underscore naming", "style")

        results = store.query_preferences(category="style")

        assert len(results) == 2
        ids = {r.context_item_id for r in results}
        assert style_pref.context_item_id in ids
        assert another_style.context_item_id in ids
        assert verb_pref.context_item_id not in ids

    def test_query_preferences_nonexistent_category(self, store):
        """Test querying preferences with nonexistent category."""
        store.add_preference("Some pref", "style")
        results = store.query_preferences(category="nonexistent")
        assert results == []

    def test_query_preferences_excludes_patterns(self, store):
        """Test that query_preferences only returns preferences, not patterns."""
        pref = store.add_preference("Pref", "style")
        pattern = store.add_pattern("Pattern", "domain")

        results = store.query_preferences()

        assert len(results) == 1
        assert results[0].context_item_id == pref.context_item_id

    # Tests for clear_all

    def test_clear_all_with_callback_approved(self, store_with_callback):
        """Test clearing all memory when user approves."""
        callback = store_with_callback.confirmation_callback
        callback.return_value = True

        # Add some items
        store_with_callback.add_preference("Pref", "style")
        store_with_callback.add_pattern("Pattern", "domain")

        assert store_with_callback.backend.count() == 2

        result = store_with_callback.clear_all()

        assert result is True
        assert store_with_callback.backend.count() == 0
        callback.assert_called_once()
        assert "DANGER" in callback.call_args[0][0]

    def test_clear_all_with_callback_denied(self, store_with_callback):
        """Test clearing all memory when user declines."""
        callback = store_with_callback.confirmation_callback
        callback.return_value = False

        # Add some items
        store_with_callback.add_preference("Pref", "style")
        store_with_callback.add_pattern("Pattern", "domain")

        assert store_with_callback.backend.count() == 2

        result = store_with_callback.clear_all()

        assert result is False
        assert store_with_callback.backend.count() == 2
        callback.assert_called_once()

    def test_clear_all_without_callback(self, store):
        """Test clearing all memory without callback."""
        # Add some items
        store.add_preference("Pref", "style")
        store.add_pattern("Pattern", "domain")

        assert store.backend.count() == 2

        result = store.clear_all()

        assert result is True
        assert store.backend.count() == 0

    # Integration tests

    def test_store_isolation(self):
        """Test that separate stores don't interfere."""
        backend1 = InMemoryBackend()
        backend2 = InMemoryBackend()

        store1 = GlobalMemoryStore(backend=backend1)
        store2 = GlobalMemoryStore(backend=backend2)

        store1.add_preference("Pref 1", "style")
        store2.add_preference("Pref 2", "style")

        results1 = store1.query_preferences()
        results2 = store2.query_preferences()

        assert len(results1) == 1
        assert len(results2) == 1
        assert results1[0].payload["preference"] == "Pref 1"
        assert results2[0].payload["preference"] == "Pref 2"

    def test_mixed_operations(self, store):
        """Test a realistic workflow of mixed operations."""
        # Add various items
        pref1 = store.add_preference("Style 1", "style")
        pref2 = store.add_preference("Verbosity 1", "verbosity")
        pattern1 = store.add_pattern("Pattern 1", "testing")
        pattern2 = store.add_pattern("Pattern 2", "documentation")

        # Verify they're all there
        all_prefs = store.query_preferences()
        assert len(all_prefs) == 2

        # Query by category
        style_prefs = store.query_preferences(category="style")
        assert len(style_prefs) == 1
        assert style_prefs[0].context_item_id == pref1.context_item_id

        # Backend should have all items
        assert store.backend.count() == 4

        # Clear everything
        assert store.clear_all() is True
        assert store.backend.count() == 0

    def test_confirmation_callback_receives_message(self, store_with_callback):
        """Test that callback receives appropriate messages."""
        callback = store_with_callback.confirmation_callback

        # Test preference message
        callback.reset_mock()
        callback.return_value = True
        store_with_callback.add_preference(
            "test pref",
            "test_category",
            require_confirmation=True
        )
        message = callback.call_args[0][0]
        assert "test pref" in message
        assert "test_category" in message
        assert "Add global preference" in message

        # Test clear_all message
        callback.reset_mock()
        callback.return_value = True
        store_with_callback.clear_all()
        message = callback.call_args[0][0]
        assert "DANGER" in message
        assert "Clear ALL" in message
        assert "cannot be undone" in message

    def test_item_uniqueness(self, store):
        """Test that each item gets a unique ID."""
        items = []
        for i in range(10):
            item = store.add_preference(f"Pref {i}", "style")
            items.append(item)

        ids = {item.context_item_id for item in items}
        assert len(ids) == 10  # All unique

    def test_source_field_consistency(self, store):
        """Test that all items have 'global' as source."""
        pref = store.add_preference("Pref", "style")
        pattern = store.add_pattern("Pattern", "domain")

        assert pref.source == "global"
        assert pattern.source == "global"

    def test_timestamp_field_present(self, store):
        """Test that items have timestamps."""
        pref = store.add_preference("Pref", "style")
        pattern = store.add_pattern("Pattern", "domain")

        assert pref.timestamp is not None
        assert pattern.timestamp is not None
        # Timestamps should be ISO format strings
        assert "T" in pref.timestamp  # ISO format includes 'T'
        assert "T" in pattern.timestamp


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
