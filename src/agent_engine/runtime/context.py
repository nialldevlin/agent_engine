"""Context assembler and simple in-memory stores."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from agent_engine.schemas import ContextItem, ContextPackage, ContextRequest, Task, MemoryConfig


@dataclass
class ContextStore:
    items: Dict[str, ContextItem] = field(default_factory=dict)

    def add(self, item: ContextItem) -> None:
        self.items[item.context_item_id] = item

    def list_items(self) -> List[ContextItem]:
        return list(self.items.values())


@dataclass
class ContextAssembler:
    store: ContextStore = field(default_factory=ContextStore)
    memory_config: Optional[MemoryConfig] = None

    def build_context(self, task: Task, request: ContextRequest) -> ContextPackage:
        # Budget-aware assembler with simple head/tail prioritization
        items = self.store.list_items()
        budget = request.budget_tokens
        selected: List[ContextItem] = []

        # Sort by importance then insertion order (as stored)
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
