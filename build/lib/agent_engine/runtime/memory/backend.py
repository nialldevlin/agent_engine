"""Memory backend interface and in-memory implementation."""

from __future__ import annotations

import operator
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

from agent_engine.schemas.memory import ContextItem


class MemoryBackend(Protocol):
    """Abstract interface for memory storage backends."""

    def add(self, item: ContextItem) -> None:
        """Add a context item to the store.

        Args:
            item: ContextItem to store

        Raises:
            MemoryError: If storage fails
        """
        ...

    def query(
        self,
        filters: Dict[str, Any],
        limit: int = 100,
        order_by: str = "timestamp"
    ) -> List[ContextItem]:
        """Query items matching filters.

        Args:
            filters: Dict of field->value filters
                Examples:
                  {"kind": "code", "tags": ["bug_fix"]}
                  {"source": "user", "importance": {"$gte": 0.7}}
            limit: Maximum items to return
            order_by: Field to sort by (default: timestamp desc)

        Returns:
            List of matching ContextItems, ordered
        """
        ...

    def get(self, item_id: str) -> Optional[ContextItem]:
        """Get item by ID.

        Args:
            item_id: Context item ID

        Returns:
            ContextItem if found, None otherwise
        """
        ...

    def delete(self, item_id: str) -> bool:
        """Delete item by ID.

        Args:
            item_id: Context item ID

        Returns:
            True if deleted, False if not found
        """
        ...

    def list_all(self) -> List[ContextItem]:
        """List all items in store.

        Returns:
            All ContextItems
        """
        ...

    def clear(self) -> None:
        """Clear all items from store."""
        ...

    def count(self) -> int:
        """Count items in store.

        Returns:
            Number of items
        """
        ...


@dataclass
class InMemoryBackend:
    """Simple in-memory implementation of MemoryBackend.

    Suitable for:
    - Development and testing
    - Task memory (ephemeral)
    - Small-scale deployments

    Not suitable for:
    - Large-scale production (use SQLite/Redis backend)
    - Persistent project/global memory (use file-backed backend)
    """

    items: Dict[str, ContextItem] = field(default_factory=dict)

    def add(self, item: ContextItem) -> None:
        self.items[item.context_item_id] = item

    def query(
        self,
        filters: Dict[str, Any],
        limit: int = 100,
        order_by: str = "timestamp"
    ) -> List[ContextItem]:
        # Filter items
        results = []
        for item in self.items.values():
            if self._matches_filters(item, filters):
                results.append(item)

        # Sort
        reverse = True  # Newest first by default
        if order_by.startswith("-"):
            order_by = order_by[1:]
            reverse = False

        results.sort(
            key=lambda i: getattr(i, order_by, None) or "",
            reverse=reverse
        )

        return results[:limit]

    def _matches_filters(self, item: ContextItem, filters: Dict[str, Any]) -> bool:
        """Check if item matches all filters."""
        for field, value in filters.items():
            item_value = getattr(item, field, None)

            # Handle dict-based operators like {"$gte": 0.7}
            if isinstance(value, dict):
                for op, op_value in value.items():
                    if not self._apply_operator(item_value, op, op_value):
                        return False
            # Handle list membership (tags)
            elif isinstance(value, list):
                if not isinstance(item_value, list):
                    return False
                if not any(v in item_value for v in value):
                    return False
            # Exact match
            else:
                if item_value != value:
                    return False

        return True

    def _apply_operator(self, value: Any, op: str, target: Any) -> bool:
        """Apply a comparison operator.

        Returns False if value is None (cannot compare None with any operator).
        """
        # Cannot compare None with most operators (except maybe $eq/$ne)
        if value is None:
            if op == "$eq":
                return target is None
            elif op == "$ne":
                return target is not None
            else:
                return False

        ops = {
            "$eq": operator.eq,
            "$ne": operator.ne,
            "$gt": operator.gt,
            "$gte": operator.ge,
            "$lt": operator.lt,
            "$lte": operator.le,
        }
        if op in ops:
            try:
                return ops[op](value, target)
            except (TypeError, AttributeError):
                return False
        return False

    def get(self, item_id: str) -> Optional[ContextItem]:
        return self.items.get(item_id)

    def delete(self, item_id: str) -> bool:
        if item_id in self.items:
            del self.items[item_id]
            return True
        return False

    def list_all(self) -> List[ContextItem]:
        return list(self.items.values())

    def clear(self) -> None:
        self.items.clear()

    def count(self) -> int:
        return len(self.items)
