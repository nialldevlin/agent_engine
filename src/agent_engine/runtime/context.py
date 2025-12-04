"""Context assembler with multi-tier memory system."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from agent_engine.schemas import ContextItem, ContextPackage, ContextRequest, Task, MemoryConfig
from agent_engine.runtime.memory import (
    TaskMemoryStore,
    ProjectMemoryStore,
    GlobalMemoryStore,
    InMemoryBackend,
)


@dataclass
class ContextStore:
    """DEPRECATED: Legacy single-tier context store.

    Kept for backward compatibility. New code should use ContextAssembler
    with multi-tier memory stores (task/project/global).
    """
    items: Dict[str, ContextItem] = field(default_factory=dict)

    def add(self, item: ContextItem) -> None:
        self.items[item.context_item_id] = item

    def list_items(self) -> List[ContextItem]:
        return list(self.items.values())


@dataclass
class ContextAssembler:
    """Assembles context from multi-tier memory stores.

    Three-tier architecture:
    - Task Memory: Ephemeral, task-scoped (cleared on completion)
    - Project Memory: Persistent, project-scoped (isolated by project_id)
    - Global Memory: Persistent, cross-project (user preferences)

    Migration note: Old 'store' field kept for backward compatibility.
    """

    # Legacy field (deprecated)
    store: Optional[ContextStore] = None

    # Multi-tier memory stores
    task_stores: Dict[str, TaskMemoryStore] = field(default_factory=dict)
    project_stores: Dict[str, ProjectMemoryStore] = field(default_factory=dict)
    global_store: GlobalMemoryStore = field(default_factory=lambda: GlobalMemoryStore(
        backend=InMemoryBackend()
    ))

    memory_config: Optional[MemoryConfig] = None

    def build_context(self, task: Task, request: ContextRequest) -> ContextPackage:
        """Build context package from all memory tiers.

        Process:
        1. Get or create task memory store
        2. Get or create project memory store (from task metadata)
        3. Query all three tiers (task/project/global)
        4. Allocate budget across tiers
        5. Select items within budget using HEAD/TAIL + importance
        6. Return ContextPackage with compression ratio

        Backward compatibility: Falls back to old store if multi-tier not set up.
        """

        # Backward compatibility: use old store if present and no task stores
        if self.store and not self.task_stores:
            return self._build_context_legacy(task, request)

        # Get or create task store
        task_store = self.task_stores.get(task.task_id)
        if not task_store:
            task_store = TaskMemoryStore(task_id=task.task_id)
            self.task_stores[task.task_id] = task_store

        # Get or create project store (from task spec metadata)
        project_id = task.spec.metadata.get("project_id", "default")
        project_store = self.project_stores.get(project_id)
        if not project_store:
            project_store = ProjectMemoryStore(
                project_id=project_id,
                backend=InMemoryBackend()  # TODO: file-backed in future
            )
            self.project_stores[project_id] = project_store

        # Query all three tiers
        budget = request.budget_tokens
        budget_allocation = self._get_budget_allocation(request)

        task_items = task_store.backend.list_all()
        project_items = project_store.backend.query(
            filters={},
            limit=budget_allocation["project"] // 10  # Assume ~10 tokens/item
        )
        global_items = self.global_store.backend.query(
            filters={},
            limit=budget_allocation["global"] // 10
        )

        # Combine and select within budget
        all_items = task_items + project_items + global_items
        selected = self._select_within_budget(all_items, budget, request)

        # Compute compression ratio
        total_cost = sum(i.token_cost or 0 for i in all_items) or 1
        current_cost = sum(i.token_cost or 0 for i in selected)
        compression_ratio = current_cost / total_cost

        return ContextPackage(
            context_package_id=f"ctx-{task.task_id}",
            items=selected,
            summary=None,
            compression_ratio=compression_ratio
        )

    def _build_context_legacy(self, task: Task, request: ContextRequest) -> ContextPackage:
        """Legacy context building (backward compatibility)."""
        items = self.store.list_items() if self.store else []
        budget = request.budget_tokens
        selected: List[ContextItem] = []

        # Sort by importance then insertion order
        items_sorted = sorted(items, key=lambda i: (-(i.importance or 0), i.timestamp or ""))

        head_tail_preserve = None
        if self.memory_config and self.memory_config.context_policy:
            head_tail_preserve = self.memory_config.context_policy.head_tail_preserve

        if head_tail_preserve:
            head = items_sorted[:head_tail_preserve]
            tail = items_sorted[-head_tail_preserve:] if head_tail_preserve > 0 else []
            items_sorted = head + [i for i in items_sorted if i not in head and i not in tail] + tail

        current_tokens = 0
        for item in items_sorted:
            cost = item.token_cost or 0
            if budget and current_tokens + cost > budget:
                continue
            selected.append(item)
            current_tokens += cost

        compression_ratio = None
        if budget and items:
            total_cost = sum(i.token_cost or 0 for i in items) or 1
            compression_ratio = min(1.0, current_tokens / total_cost)

        return ContextPackage(
            context_package_id=f"ctx-{getattr(task, 'task_id', 'unknown')}",
            items=selected,
            summary=None,
            compression_ratio=compression_ratio,
        )

    def _get_budget_allocation(self, request: ContextRequest) -> Dict[str, int]:
        """Allocate budget across memory tiers.

        Default allocation:
        - Task: 40% (current task context)
        - Project: 40% (project-specific knowledge)
        - Global: 20% (user preferences)
        """
        budget = request.budget_tokens
        return {
            "task": int(budget * 0.4),
            "project": int(budget * 0.4),
            "global": int(budget * 0.2)
        }

    def _select_within_budget(
        self,
        items: List[ContextItem],
        budget: int,
        request: ContextRequest
    ) -> List[ContextItem]:
        """Select items within budget using HEAD/TAIL + importance.

        Process:
        1. Sort by importance (descending)
        2. Apply HEAD/TAIL preservation if configured
        3. Select items until budget exhausted
        """
        # Sort by importance (descending), then timestamp
        items_sorted = sorted(items, key=lambda i: (-(i.importance or 0), i.timestamp or ""))

        # Apply HEAD/TAIL preservation if configured
        head_tail_preserve = None
        if self.memory_config and self.memory_config.context_policy:
            head_tail_preserve = self.memory_config.context_policy.head_tail_preserve

        if head_tail_preserve and len(items_sorted) > head_tail_preserve * 2:
            head = items_sorted[:head_tail_preserve]
            tail = items_sorted[-head_tail_preserve:]
            middle = [i for i in items_sorted if i not in head and i not in tail]
            items_sorted = head + middle + tail

        # Select within budget
        selected = []
        current_tokens = 0
        for item in items_sorted:
            cost = item.token_cost or 0
            if current_tokens + cost <= budget:
                selected.append(item)
                current_tokens += cost

            if current_tokens >= budget:
                break

        return selected

    def cleanup_task(self, task_id: str) -> None:
        """Clean up task memory when task completes.

        Removes ephemeral task memory store to free resources.
        Project and global memory persist.
        """
        if task_id in self.task_stores:
            self.task_stores[task_id].clear()
            del self.task_stores[task_id]
