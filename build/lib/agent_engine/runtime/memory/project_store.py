"""Project memory store for persistent project-specific context."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from agent_engine.schemas.errors import FailureSignature
from agent_engine.schemas.memory import ContextItem

from .backend import MemoryBackend


@dataclass
class ProjectMemoryStore:
    """Persistent memory for a specific project.

    Stores project-specific knowledge that persists across tasks.
    Isolated by project_id - projects cannot access each other's memory.
    """

    project_id: str
    backend: MemoryBackend
    max_items: int = 1000

    def add_decision(self, decision: str, tags: List[str]) -> ContextItem:
        """Add a design decision.

        Args:
            decision: The decision text
            tags: List of tags for the decision

        Returns:
            ContextItem for the added decision
        """
        item = ContextItem(
            context_item_id=f"decision-{uuid4()}",
            kind="decision",
            source=f"project/{self.project_id}",
            timestamp=datetime.now().isoformat(),
            tags=["project", "decision"] + tags,
            importance=0.9,
            token_cost=len(decision.split()),
            payload={"decision": decision}
        )
        self.backend.add(item)
        self._maybe_evict()
        return item

    def add_convention(self, convention: str, scope: str) -> ContextItem:
        """Add a coding convention.

        Args:
            convention: The convention text
            scope: Scope of the convention (e.g., 'python', 'tests')

        Returns:
            ContextItem for the added convention
        """
        item = ContextItem(
            context_item_id=f"convention-{uuid4()}",
            kind="convention",
            source=f"project/{self.project_id}",
            timestamp=datetime.now().isoformat(),
            tags=["project", "convention", scope],
            importance=0.8,
            token_cost=len(convention.split()),
            payload={"convention": convention, "scope": scope}
        )
        self.backend.add(item)
        self._maybe_evict()
        return item

    def add_failure(self, failure: FailureSignature, lesson: str) -> ContextItem:
        """Add an important failure and lesson learned.

        Args:
            failure: The FailureSignature
            lesson: The lesson learned from this failure

        Returns:
            ContextItem for the added failure
        """
        item = ContextItem(
            context_item_id=f"failure-{uuid4()}",
            kind="failure",
            source=f"project/{self.project_id}",
            timestamp=datetime.now().isoformat(),
            tags=["project", "failure", failure.code.value],
            importance=0.85,
            token_cost=len(lesson.split()),
            payload={"failure": failure.model_dump(), "lesson": lesson}
        )
        self.backend.add(item)
        self._maybe_evict()
        return item

    def query_decisions(self, tags: Optional[List[str]] = None) -> List[ContextItem]:
        """Query design decisions, optionally filtered by tags.

        Args:
            tags: Optional list of tags to filter by

        Returns:
            List of ContextItems matching the query
        """
        filters = {"kind": "decision", "source": f"project/{self.project_id}"}
        if tags:
            filters["tags"] = tags
        return self.backend.query(filters, limit=100)

    def _maybe_evict(self) -> None:
        """Evict low-importance old items if over threshold."""
        if self.backend.count() > self.max_items:
            # Get all items sorted by importance (ascending) then age (oldest first)
            all_items = self.backend.list_all()
            all_items.sort(key=lambda i: (i.importance or 0, i.timestamp or ""))

            # Evict bottom 10%
            to_evict = all_items[:len(all_items) // 10]
            for item in to_evict:
                self.backend.delete(item.context_item_id)
