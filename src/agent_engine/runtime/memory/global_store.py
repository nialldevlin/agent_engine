"""Global memory store for cross-project persistent memory."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from agent_engine.schemas.memory import ContextItem

from .backend import MemoryBackend


@dataclass
class GlobalMemoryStore:
    """Global memory shared across all projects.

    Stores user preferences, cross-project patterns, and global learning.
    Writes require confirmation for high-risk items.
    """

    backend: MemoryBackend
    confirmation_callback: Optional[Callable[[str], bool]] = None

    def add_preference(
        self,
        preference: str,
        category: str,
        require_confirmation: bool = False
    ) -> Optional[ContextItem]:
        """Add a user preference.

        Args:
            preference: The preference text
            category: Category (e.g., 'style', 'verbosity', 'tools')
            require_confirmation: If True, ask user before writing

        Returns:
            ContextItem if added, None if user declined
        """
        if require_confirmation and self.confirmation_callback:
            if not self.confirmation_callback(
                f"Add global preference: '{preference}' (category: {category})?"
            ):
                return None

        item = ContextItem(
            context_item_id=f"pref-{uuid4()}",
            kind="preference",
            source="global",
            timestamp=datetime.now().isoformat(),
            tags=["global", "preference", category],
            importance=0.9,
            token_cost=len(preference.split()),
            payload={"preference": preference, "category": category}
        )
        self.backend.add(item)
        return item

    def add_pattern(self, pattern: str, domain: str) -> ContextItem:
        """Add a reusable pattern.

        Args:
            pattern: The pattern text
            domain: Domain (e.g., 'python', 'testing', 'documentation')

        Returns:
            ContextItem for the added pattern
        """
        item = ContextItem(
            context_item_id=f"pattern-{uuid4()}",
            kind="pattern",
            source="global",
            timestamp=datetime.now().isoformat(),
            tags=["global", "pattern", domain],
            importance=0.7,
            token_cost=len(pattern.split()),
            payload={"pattern": pattern, "domain": domain}
        )
        self.backend.add(item)
        return item

    def query_preferences(self, category: Optional[str] = None) -> List[ContextItem]:
        """Query user preferences.

        Args:
            category: Optional category filter

        Returns:
            List of ContextItems matching query
        """
        filters: Dict[str, Any] = {"kind": "preference", "source": "global"}
        if category:
            filters["tags"] = [category]
        return self.backend.query(filters, limit=100)

    def clear_all(self) -> bool:
        """Clear all global memory (requires confirmation).

        Returns:
            True if cleared, False if user declined or callback not set
        """
        if self.confirmation_callback:
            if not self.confirmation_callback(
                "DANGER: Clear ALL global memory? This cannot be undone."
            ):
                return False
        self.backend.clear()
        return True
