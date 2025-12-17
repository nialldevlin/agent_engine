"""Memory store initialization and implementation with persistence support."""

from typing import Dict, List, Any, Optional
from pathlib import Path
from .schemas.memory import ContextProfile, ContextProfileSource
from .runtime.persistent_memory import PersistentMemoryStore


class MemoryStore:
    """Memory store with optional persistence backends.

    Supports in-memory, JSONL, and SQLite backends with automatic persistence
    and retention policies per Phase 19.
    """

    def __init__(
        self,
        store_id: str,
        store_type: str = "in_memory",
        backend: Optional[str] = None,
        file_path: Optional[str] = None,
        db_path: Optional[str] = None,
        max_items: Optional[int] = None
    ):
        """Initialize a memory store with optional persistence.

        Args:
            store_id: Unique identifier for this store (e.g., 'task', 'project', 'global').
            store_type: Type of store (deprecated, use backend).
            backend: Storage backend ('in_memory', 'jsonl', 'sqlite').
            file_path: Path for JSONL backend.
            db_path: Path for SQLite backend.
            max_items: Retention policy - maximum items to keep.
        """
        self.store_id = store_id
        self.store_type = store_type
        self.items: List[Any] = []  # Legacy support

        # Use backend parameter if provided, fall back to store_type
        backend_type = backend or "in_memory"

        # Initialize persistent backend
        try:
            self.persistent_store = PersistentMemoryStore(
                backend_type=backend_type,
                file_path=file_path,
                db_path=db_path,
                max_items=max_items
            )
        except Exception as e:
            # Fall back to in-memory if backend init fails
            self.persistent_store = PersistentMemoryStore(
                backend_type="in_memory",
                max_items=max_items
            )

    def get(self, item_id: str) -> Optional[Any]:
        """Get item by ID.

        Args:
            item_id: Identifier of the item to retrieve.

        Returns:
            The requested item, or None if not found.
        """
        from .schemas.memory import ContextItem
        item = self.persistent_store.get(item_id)
        return item

    def put(self, item: Any) -> None:
        """Put item in store with persistence.

        Args:
            item: Item to store (should be ContextItem for persistence).
        """
        # Support legacy list appending
        self.items.append(item)

        # Also persist if it's a ContextItem
        from .schemas.memory import ContextItem
        if isinstance(item, ContextItem):
            self.persistent_store.add(item)

    def query(
        self,
        filters: Dict[str, Any],
        limit: int = 100,
        order_by: str = "timestamp"
    ) -> List[Any]:
        """Query items from persistent store.

        Args:
            filters: Filter criteria dict
            limit: Max items to return
            order_by: Field to sort by

        Returns:
            List of matching items
        """
        return self.persistent_store.query(filters, limit, order_by)

    def append(self, item: Any) -> None:
        """Append item to store (legacy support).

        Args:
            item: Item to append
        """
        self.put(item)


def initialize_memory_stores(memory_config: Optional[Dict], adapter_registry=None) -> Dict[str, MemoryStore]:
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
            backend = store_config.get("backend") or store_config.get("type", "in_memory")
            # Allow adapter-registered memory store factories
            if adapter_registry:
                created = adapter_registry.create_memory_store(backend, store_id, store_config)
            else:
                created = None

            if created:
                stores[store_id] = created
            else:
                stores[store_id] = MemoryStore(
                    store_id,
                    store_config.get("type", "in_memory"),
                    backend=backend,
                    file_path=store_config.get("file_path"),
                    db_path=store_config.get("db_path"),
                    max_items=store_config.get("max_items")
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
