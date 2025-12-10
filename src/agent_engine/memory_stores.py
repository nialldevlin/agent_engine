"""Memory store initialization and stub implementation for Phase 2."""

from typing import Dict, List, Any, Optional
from .schemas.memory import ContextProfile, ContextProfileSource


class MemoryStore:
    """Stub memory store for Phase 2 (full implementation in Phase 6).

    Provides a minimal interface for memory storage with no persistence.
    This is a placeholder for the complete memory store implementation
    that will be done in Phase 6.
    """

    def __init__(self, store_id: str, store_type: str):
        """Initialize a memory store.

        Args:
            store_id: Unique identifier for this store (e.g., 'task', 'project', 'global').
            store_type: Type of store (e.g., 'in_memory', will support others in Phase 6).
        """
        self.store_id = store_id
        self.store_type = store_type
        self.items: List[Any] = []  # Stub storage

    def get(self, item_id: str) -> Optional[Any]:
        """Get item by ID (stub - returns None).

        Args:
            item_id: Identifier of the item to retrieve.

        Returns:
            The requested item, or None if not found (stub implementation).
        """
        return None

    def put(self, item: Any) -> None:
        """Put item in store (stub - no-op).

        Args:
            item: Item to store.
        """
        pass


def initialize_memory_stores(memory_config: Optional[Dict]) -> Dict[str, MemoryStore]:
    """Initialize memory stores from config or defaults.

    Creates and returns a dictionary of MemoryStore instances. If no configuration
    is provided, creates default stores for task, project, and global memory.

    Args:
        memory_config: Optional configuration dictionary with store definitions.
                      Expected keys: 'task_store', 'project_store', 'global_store'.

    Returns:
        Dictionary mapping store identifiers to MemoryStore instances.
        Default identifiers: 'task', 'project', 'global'.
    """
    if memory_config is None:
        # Create default stores
        return {
            "task": MemoryStore("task", "in_memory"),
            "project": MemoryStore("project", "in_memory"),
            "global": MemoryStore("global", "in_memory")
        }

    # Create stores from config
    stores = {}
    for store_name in ["task_store", "project_store", "global_store"]:
        if store_name in memory_config:
            store_config = memory_config[store_name]
            store_id = store_name.replace("_store", "")
            stores[store_id] = MemoryStore(
                store_id,
                store_config.get("type", "in_memory")
            )

    return stores


def initialize_context_profiles(memory_config: Optional[Dict]) -> Dict[str, ContextProfile]:
    """Initialize context profiles from config or defaults.

    Creates and returns a dictionary of ContextProfile instances. If no configuration
    is provided or no context profiles are defined, creates a default global profile
    that can retrieve from all memory stores.

    Per AGENT_ENGINE_SPEC §4, every context assembly requires at least one profile.
    This ensures nodes always have a way to access memory when needed.

    Args:
        memory_config: Optional configuration dictionary with profile definitions.
                      Expected key: 'context_profiles' (list of profile dicts).

    Returns:
        Dictionary mapping profile identifiers to ContextProfile instances.
        Always contains at least one profile: 'global_default'.
    """
    if memory_config is None or 'context_profiles' not in memory_config:
        # Create default global profile
        default_profile = ContextProfile(
            id="global_default",
            max_tokens=8000,
            retrieval_policy="recency",
            sources=[
                ContextProfileSource(store="task", tags=[]),
                ContextProfileSource(store="project", tags=[]),
                ContextProfileSource(store="global", tags=[])
            ]
        )
        return {"global_default": default_profile}

    # Load profiles from config
    profiles = {}
    for profile_dict in memory_config['context_profiles']:
        profile = ContextProfile(**profile_dict)
        profiles[profile.id] = profile

    return profiles
