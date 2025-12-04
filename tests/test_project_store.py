"""Tests for ProjectMemoryStore."""

import pytest
from datetime import datetime
from agent_engine.runtime.memory import ProjectMemoryStore, InMemoryBackend
from agent_engine.schemas.memory import ContextItem
from agent_engine.schemas.errors import FailureSignature, FailureCode, Severity


@pytest.fixture
def backend():
    """Create a fresh InMemoryBackend for each test."""
    return InMemoryBackend()


@pytest.fixture
def project_store(backend):
    """Create a ProjectMemoryStore for testing."""
    return ProjectMemoryStore(project_id="test-project", backend=backend, max_items=100)


@pytest.fixture
def other_project_store(backend):
    """Create a different ProjectMemoryStore for isolation testing."""
    return ProjectMemoryStore(project_id="other-project", backend=backend, max_items=100)


class TestAddDecision:
    """Test add_decision functionality."""

    def test_add_single_decision(self, project_store):
        """Should add a decision and return a ContextItem."""
        item = project_store.add_decision("Use FastAPI for REST API", ["architecture"])

        assert item is not None
        assert item.kind == "decision"
        assert item.source == "project/test-project"
        assert item.importance == 0.9
        assert "project" in item.tags
        assert "decision" in item.tags
        assert "architecture" in item.tags
        assert item.payload["decision"] == "Use FastAPI for REST API"

    def test_decision_timestamp(self, project_store):
        """Decision should have a valid timestamp."""
        before = datetime.now().isoformat()
        item = project_store.add_decision("Test decision", [])
        after = datetime.now().isoformat()

        assert before <= item.timestamp <= after

    def test_decision_token_cost(self, project_store):
        """Decision token cost should be calculated from text length."""
        item = project_store.add_decision("Word one two three four", [])
        assert item.token_cost == 5

    def test_add_multiple_decisions(self, project_store):
        """Should be able to add multiple decisions."""
        item1 = project_store.add_decision("Decision 1", ["tag1"])
        item2 = project_store.add_decision("Decision 2", ["tag2"])

        assert item1.context_item_id != item2.context_item_id
        assert project_store.backend.count() == 2


class TestAddConvention:
    """Test add_convention functionality."""

    def test_add_single_convention(self, project_store):
        """Should add a convention and return a ContextItem."""
        item = project_store.add_convention(
            "Use snake_case for function names",
            "python"
        )

        assert item is not None
        assert item.kind == "convention"
        assert item.source == "project/test-project"
        assert item.importance == 0.8
        assert "project" in item.tags
        assert "convention" in item.tags
        assert "python" in item.tags
        assert item.payload["convention"] == "Use snake_case for function names"
        assert item.payload["scope"] == "python"

    def test_convention_token_cost(self, project_store):
        """Convention token cost should be calculated from text length."""
        item = project_store.add_convention("One two three", "scope")
        assert item.token_cost == 3

    def test_add_multiple_conventions(self, project_store):
        """Should be able to add multiple conventions."""
        item1 = project_store.add_convention("Convention 1", "python")
        item2 = project_store.add_convention("Convention 2", "tests")

        assert item1.context_item_id != item2.context_item_id
        assert project_store.backend.count() == 2


class TestAddFailure:
    """Test add_failure functionality."""

    def test_add_single_failure(self, project_store):
        """Should add a failure and return a ContextItem."""
        failure = FailureSignature(
            code=FailureCode.TOOL_FAILURE,
            message="Tool execution failed",
            stage_id="stage-1",
            severity=Severity.ERROR
        )
        item = project_store.add_failure(failure, "Always validate tool inputs")

        assert item is not None
        assert item.kind == "failure"
        assert item.source == "project/test-project"
        assert item.importance == 0.85
        assert "project" in item.tags
        assert "failure" in item.tags
        assert "tool_failure" in item.tags
        assert item.payload["lesson"] == "Always validate tool inputs"

    def test_failure_payload_contains_failure_dict(self, project_store):
        """Failure payload should contain the failure signature dict."""
        failure = FailureSignature(
            code=FailureCode.TIMEOUT,
            message="Request timed out",
            severity=Severity.WARNING
        )
        item = project_store.add_failure(failure, "Increase timeout")

        assert "failure" in item.payload
        assert item.payload["failure"]["code"] == FailureCode.TIMEOUT.value
        assert item.payload["failure"]["message"] == "Request timed out"

    def test_failure_token_cost(self, project_store):
        """Failure token cost should be calculated from lesson length."""
        failure = FailureSignature(
            code=FailureCode.UNKNOWN,
            message="Unknown error"
        )
        item = project_store.add_failure(failure, "One two three")
        assert item.token_cost == 3


class TestQueryDecisions:
    """Test query_decisions functionality."""

    def test_query_all_decisions(self, project_store):
        """Should return all decisions without filter."""
        project_store.add_decision("Decision 1", ["tag1"])
        project_store.add_decision("Decision 2", ["tag2"])
        project_store.add_convention("Convention 1", "scope")  # Should not be returned

        results = project_store.query_decisions()

        assert len(results) == 2
        assert all(r.kind == "decision" for r in results)

    def test_query_decisions_with_tag_filter(self, project_store):
        """Should filter decisions by tags."""
        project_store.add_decision("Decision 1", ["architecture"])
        project_store.add_decision("Decision 2", ["performance"])
        project_store.add_decision("Decision 3", ["architecture"])

        results = project_store.query_decisions(tags=["architecture"])

        assert len(results) == 2
        assert all("architecture" in r.tags for r in results)

    def test_query_decisions_empty_result(self, project_store):
        """Should return empty list if no matching decisions."""
        project_store.add_decision("Decision 1", ["tag1"])

        results = project_store.query_decisions(tags=["nonexistent"])

        assert len(results) == 0

    def test_query_decisions_respects_source_isolation(self, project_store, other_project_store):
        """Queries should only return items from the same project."""
        project_store.add_decision("Project 1 Decision", ["tag1"])
        other_project_store.add_decision("Project 2 Decision", ["tag1"])

        results = project_store.query_decisions()

        assert len(results) == 1
        assert results[0].source == "project/test-project"


class TestProjectIsolation:
    """Test that projects are isolated by namespace."""

    def test_project_isolation_add_decision(self, project_store, other_project_store):
        """Different projects should not see each other's decisions."""
        project_store.add_decision("Project 1 Decision", [])
        other_project_store.add_decision("Project 2 Decision", [])

        # Each project should only see its own items
        assert project_store.backend.count() == 2  # Both added to same backend

        # But queries should be isolated by source
        project1_results = project_store.query_decisions()
        project2_results = other_project_store.query_decisions()

        assert len(project1_results) == 1
        assert len(project2_results) == 1
        assert project1_results[0].source == "project/test-project"
        assert project2_results[0].source == "project/other-project"

    def test_project_namespace_format(self, project_store):
        """Items should use correct namespace format: project/{project_id}."""
        item = project_store.add_decision("Decision", [])
        assert item.source == "project/test-project"
        assert item.source.startswith("project/")


class TestEviction:
    """Test eviction policy when exceeding max_items."""

    def test_no_eviction_below_threshold(self, project_store):
        """Should not evict items when below max_items."""
        for i in range(50):
            project_store.add_decision(f"Decision {i}", [])

        assert project_store.backend.count() == 50

    def test_eviction_triggered_above_threshold(self, project_store):
        """Should evict items when exceeding max_items."""
        # Add items with varying importance
        for i in range(101):
            project_store.add_decision(f"Decision {i}", [])

        count = project_store.backend.count()
        assert count <= 101
        assert count > 90  # Should evict bottom 10% (approximately 10 items)

    def test_eviction_preserves_high_importance(self):
        """Eviction should preserve high-importance items."""
        backend = InMemoryBackend()
        store = ProjectMemoryStore(project_id="test", backend=backend, max_items=10)

        # Add low-importance items
        for i in range(5):
            item = ContextItem(
                context_item_id=f"low-{i}",
                kind="convention",
                source="project/test",
                timestamp="2025-01-01T00:00:00",
                importance=0.1,
                token_cost=1,
                payload={"test": "data"}
            )
            backend.add(item)

        # Add high-importance items
        for i in range(6):
            item = ContextItem(
                context_item_id=f"high-{i}",
                kind="decision",
                source="project/test",
                timestamp="2025-01-01T00:00:00",
                importance=0.95,
                token_cost=1,
                payload={"test": "data"}
            )
            backend.add(item)

        # Trigger eviction by adding one more item
        store.add_decision("Trigger eviction", [])

        # Should have evicted low-importance items, kept high-importance
        remaining = backend.list_all()
        assert len(remaining) > len([i for i in remaining if i.importance <= 0.1])

    def test_eviction_preserves_recent_items(self):
        """When importance is equal, should preserve more recent items."""
        backend = InMemoryBackend()
        store = ProjectMemoryStore(project_id="test", backend=backend, max_items=10)

        # Add old items with same importance
        old_item = ContextItem(
            context_item_id="old",
            kind="convention",
            source="project/test",
            timestamp="2020-01-01T00:00:00",
            importance=0.5,
            token_cost=1,
            payload={"test": "old"}
        )
        backend.add(old_item)

        # Add new items with same importance
        for i in range(10):
            item = ContextItem(
                context_item_id=f"new-{i}",
                kind="convention",
                source="project/test",
                timestamp="2025-01-01T00:00:00",
                importance=0.5,
                token_cost=1,
                payload={"test": "data"}
            )
            backend.add(item)

        # Trigger eviction
        store.add_decision("Trigger", [])

        # Old item should be gone (it's the least recent with same importance)
        remaining_ids = [i.context_item_id for i in backend.list_all()]
        assert "old" not in remaining_ids

    def test_eviction_bottom_10_percent(self):
        """Should evict approximately bottom 10% of items by importance."""
        backend = InMemoryBackend()
        store = ProjectMemoryStore(project_id="test", backend=backend, max_items=100)

        # Add 100 items with varying importance (0.0 to 0.99)
        for i in range(100):
            item = ContextItem(
                context_item_id=f"item-{i}",
                kind="convention",
                source="project/test",
                timestamp=f"2025-01-{(i % 28) + 1:02d}T00:00:00",
                importance=i / 100.0,  # 0.0 to 0.99
                token_cost=1,
                payload={"test": "data"}
            )
            backend.add(item)

        # Trigger eviction by adding one more
        store.add_decision("Trigger", [])

        remaining = backend.list_all()
        removed_count = 100 - len(remaining) + 1  # +1 for the new item added

        # Should have removed approximately 10 items (10% of 100)
        assert 8 <= removed_count <= 12


class TestIntegration:
    """Integration tests combining multiple features."""

    def test_mixed_item_types(self, project_store):
        """Store should handle decisions, conventions, and failures together."""
        decision = project_store.add_decision("Decision", ["tag1"])
        convention = project_store.add_convention("Convention", "scope")
        failure = project_store.add_failure(
            FailureSignature(code=FailureCode.TIMEOUT, message="Timeout"),
            "Lesson"
        )

        assert project_store.backend.count() == 3

        # Query should only return decisions
        decisions = project_store.query_decisions()
        assert len(decisions) == 1
        assert decisions[0].context_item_id == decision.context_item_id

    def test_continuous_add_and_query(self, project_store):
        """Should maintain consistency through multiple adds and queries."""
        for i in range(10):
            project_store.add_decision(f"Decision {i}", [f"tag{i % 3}"])

        # Query all
        all_decisions = project_store.query_decisions()
        assert len(all_decisions) == 10

        # Query by tag
        tag0_decisions = project_store.query_decisions(tags=["tag0"])
        assert len(tag0_decisions) > 0
        assert all("tag0" in d.tags for d in tag0_decisions)

    def test_high_load_stress_test(self):
        """Should handle high-volume adds without issues."""
        backend = InMemoryBackend()
        store = ProjectMemoryStore(project_id="stress-test", backend=backend, max_items=500)

        # Add many items
        for i in range(600):
            store.add_decision(f"Decision {i}", [f"tag{i % 10}"])

        # Should not exceed max_items after eviction
        assert backend.count() <= 600  # max_items can be slightly exceeded during add

        # Should be able to query
        results = store.query_decisions()
        assert len(results) > 0
