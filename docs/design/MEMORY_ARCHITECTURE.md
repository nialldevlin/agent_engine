# Memory Architecture Design

**Design Phase:** Phase 1.1 (PLAN_SONNET_MINION.md)
**Designer:** Sonnet
**Date:** 2025-12-03
**References:** RESEARCH.md §1.2 (MemGPT), §8.2 (Global vs Project Memory)

---

## Overview

This design implements a **MemGPT-style virtual memory system** with three distinct tiers, treating memory like an OS-style pager rather than a simple sliding window.

**Design Principles:**
1. **Separation of Concerns:** task/project/global tiers are isolated
2. **Explicit Paging:** data moves between tiers via explicit policies, not automatic promotion
3. **Namespace Isolation:** projects cannot access each other's memory
4. **Pluggable Backend:** in-memory for now, designed for future persistence (SQLite, Redis, etc.)

---

## Memory Tier Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    ContextAssembler                      │
│  (queries all 3 tiers, assembles ContextPackage)        │
└──────────────┬──────────────┬──────────────┬────────────┘
               │              │              │
        ┌──────▼──────┐ ┌─────▼──────┐ ┌────▼──────┐
        │   Task      │ │  Project   │ │  Global   │
        │   Memory    │ │  Memory    │ │  Memory   │
        │   Store     │ │  Store     │ │  Store    │
        └──────┬──────┘ └─────┬──────┘ └────┬──────┘
               │              │              │
               └──────────────┴──────────────┘
                              │
                    ┌─────────▼──────────┐
                    │  MemoryBackend     │
                    │  (Interface)       │
                    └────────────────────┘
```

---

## 1. Memory Backend Interface

**File:** `src/agent_engine/runtime/memory/backend.py`

### 1.1 Core Interface

```python
from typing import Protocol, List, Dict, Any, Optional
from agent_engine.schemas import ContextItem

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
```

### 1.2 InMemoryBackend Implementation

**File:** `src/agent_engine/runtime/memory/backend.py`

```python
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
import operator
from agent_engine.schemas import ContextItem

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
        ops = {
            "$eq": operator.eq,
            "$ne": operator.ne,
            "$gt": operator.gt,
            "$gte": operator.ge,
            "$lt": operator.lt,
            "$lte": operator.le,
        }
        if op in ops:
            return ops[op](value, target)
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
```

---

## 2. Task Memory Store

**File:** `src/agent_engine/runtime/memory/task_store.py`

### 2.1 Purpose

Ephemeral storage for **current task only**:
- Intermediate reasoning
- Tool outputs from this task
- Partial plans and results
- Temporary context

**Lifecycle:** Created with task, destroyed when task completes

**Access Pattern:** Fast, frequent reads/writes during task execution

### 2.2 Design

```python
@dataclass
class TaskMemoryStore:
    """Ephemeral memory for a single task.

    Automatically cleared when task completes.
    Optimized for fast access during task execution.
    """

    task_id: str
    backend: MemoryBackend = field(default_factory=InMemoryBackend)

    def add_reasoning(self, text: str, stage_id: str) -> ContextItem:
        """Add reasoning from a stage."""
        item = ContextItem(
            context_item_id=f"reasoning-{stage_id}-{uuid4()}",
            kind="reasoning",
            source=f"task/{self.task_id}/{stage_id}",
            timestamp=datetime.now().isoformat(),
            tags=["task", stage_id],
            importance=0.5,
            token_cost=len(text.split()),
            payload={"text": text}
        )
        self.backend.add(item)
        return item

    def add_tool_output(self, tool_id: str, output: Any) -> ContextItem:
        """Add tool execution output."""
        item = ContextItem(
            context_item_id=f"tool-{tool_id}-{uuid4()}",
            kind="tool_output",
            source=f"task/{self.task_id}",
            timestamp=datetime.now().isoformat(),
            tags=["task", "tool", tool_id],
            importance=0.7,
            token_cost=len(str(output).split()),
            payload={"tool_id": tool_id, "output": output}
        )
        self.backend.add(item)
        return item

    def get_stage_outputs(self, stage_id: str) -> List[ContextItem]:
        """Get all outputs from a specific stage."""
        return self.backend.query(
            filters={"source": f"task/{self.task_id}/{stage_id}"},
            limit=1000
        )

    def clear(self) -> None:
        """Clear all task memory (called on task completion)."""
        self.backend.clear()
```

### 2.3 Cleanup Policy

- **Automatic:** TaskMemoryStore.clear() called when task reaches terminal state
- **Manual:** Can be cleared earlier if task fails and won't retry
- **Preservation:** Important items can be promoted to project memory before clearing

---

## 3. Project Memory Store

**File:** `src/agent_engine/runtime/memory/project_store.py`

### 3.1 Purpose

Persistent storage for **project-specific information**:
- Design decisions for this project
- Coding conventions
- Important failures and lessons
- Project-specific patterns
- User preferences for this project

**Lifecycle:** Lives as long as project exists

**Access Pattern:** Moderate reads, low writes, needs persistence

### 3.2 Namespace Design

**Namespace:** `project/<project_id>/`

**Isolation:** Projects CANNOT access each other's memory

```
project/
  ├─ agent_engine/         # This project
  │   ├─ decisions/        # Design decisions
  │   ├─ conventions/      # Coding style
  │   ├─ failures/         # Important failures
  │   └─ patterns/         # Reusable patterns
  ├─ ros_workspace/        # Different project
  │   └─ ...
  └─ web_app/              # Another project
      └─ ...
```

### 3.3 Design

```python
@dataclass
class ProjectMemoryStore:
    """Persistent memory for a specific project.

    Stores project-specific knowledge that persists across tasks.
    Isolated by project_id - projects cannot access each other's memory.
    """

    project_id: str
    backend: MemoryBackend
    max_items: int = 1000  # Eviction threshold

    def add_decision(self, decision: str, tags: List[str]) -> ContextItem:
        """Add a design decision."""
        item = ContextItem(
            context_item_id=f"decision-{uuid4()}",
            kind="decision",
            source=f"project/{self.project_id}",
            timestamp=datetime.now().isoformat(),
            tags=["project", "decision"] + tags,
            importance=0.9,  # High importance
            token_cost=len(decision.split()),
            payload={"decision": decision}
        )
        self.backend.add(item)
        self._maybe_evict()
        return item

    def add_convention(self, convention: str, scope: str) -> ContextItem:
        """Add a coding convention."""
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
        """Add an important failure and lesson learned."""
        item = ContextItem(
            context_item_id=f"failure-{uuid4()}",
            kind="failure",
            source=f"project/{self.project_id}",
            timestamp=datetime.now().isoformat(),
            tags=["project", "failure", failure.code.value],
            importance=0.85,
            token_cost=len(lesson.split()),
            payload={"failure": failure.dict(), "lesson": lesson}
        )
        self.backend.add(item)
        self._maybe_evict()
        return item

    def query_decisions(self, tags: Optional[List[str]] = None) -> List[ContextItem]:
        """Query design decisions, optionally filtered by tags."""
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
```

### 3.4 Persistence Strategy

**Phase 1 (Current):** InMemoryBackend (lost on restart)

**Phase 2 (Future):**
- JSON file per project: `~/.agent_engine/projects/{project_id}/memory.json`
- Load on first access, save on write (with debouncing)
- Migrate to SQLite for larger projects

---

## 4. Global Memory Store

**File:** `src/agent_engine/runtime/memory/global_store.py`

### 4.1 Purpose

Cross-project persistent storage for:
- User preferences and style
- Reusable patterns and strategies
- Global learning (e.g., "always explain ROS launch changes")

**Lifecycle:** Permanent (until user explicitly clears)

**Access Pattern:** Low writes (with confirmation), moderate reads

### 4.2 Design

```python
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
        """Add a reusable pattern."""
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
        """Query user preferences."""
        filters = {"kind": "preference", "source": "global"}
        if category:
            filters["tags"] = [category]
        return self.backend.query(filters, limit=100)

    def clear_all(self) -> bool:
        """Clear all global memory (requires confirmation)."""
        if self.confirmation_callback:
            if not self.confirmation_callback(
                "DANGER: Clear ALL global memory? This cannot be undone."
            ):
                return False
        self.backend.clear()
        return True
```

### 4.3 Safety Policies

**High-Risk Operations (require confirmation):**
- Adding global preferences
- Modifying existing preferences
- Clearing all global memory

**Low-Risk Operations (no confirmation):**
- Adding patterns
- Querying memory
- Viewing preferences

---

## 5. Paging Policies

### 5.1 Context Request Flow

```
User Task
    ↓
ContextAssembler.build_context(task, request)
    ↓
Query Task Memory (fast, always included)
    ↓
Query Project Memory (filtered by relevance + budget)
    ↓
Query Global Memory (filtered by category + budget)
    ↓
Score & Rank all items
    ↓
Select within budget
    ↓
Return ContextPackage
```

### 5.2 Budget Allocation

**Default allocation:**
- Task Memory: 40% of budget (current task context)
- Project Memory: 40% of budget (project-specific)
- Global Memory: 20% of budget (user preferences)

**Adjustable per ContextRequest and agent profile**

### 5.3 Promotion/Demotion

**Promotion (manual, explicit):**
- Task → Project: Important discoveries, patterns, lessons
- Project → Global: Reusable patterns that apply across projects

**No automatic promotion** to avoid pollution

**Demotion/Eviction:**
- Task: Cleared on completion
- Project: LRU eviction when over max_items threshold
- Global: Manual clearing only

---

## 6. Integration with ContextAssembler

**File:** `src/agent_engine/runtime/context.py`

### 6.1 Updated ContextAssembler

```python
@dataclass
class ContextAssembler:
    """Assembles context from multi-tier memory stores."""

    # Replace single store with multi-tier
    task_stores: Dict[str, TaskMemoryStore] = field(default_factory=dict)
    project_stores: Dict[str, ProjectMemoryStore] = field(default_factory=dict)
    global_store: GlobalMemoryStore = field(default_factory=lambda: GlobalMemoryStore(
        backend=InMemoryBackend()
    ))
    memory_config: Optional[MemoryConfig] = None

    def build_context(self, task: Task, request: ContextRequest) -> ContextPackage:
        """Build context package from all memory tiers."""

        # Get or create task store
        task_store = self.task_stores.get(task.task_id)
        if not task_store:
            task_store = TaskMemoryStore(task_id=task.task_id)
            self.task_stores[task.task_id] = task_store

        # Get or create project store (from task metadata)
        project_id = task.metadata.get("project_id", "default")
        project_store = self.project_stores.get(project_id)
        if not project_store:
            project_store = ProjectMemoryStore(
                project_id=project_id,
                backend=InMemoryBackend()  # TODO: file-backed
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

        # Combine and score
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

    def _get_budget_allocation(self, request: ContextRequest) -> Dict[str, int]:
        """Allocate budget across tiers."""
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
        """Select items within budget using HEAD/TAIL + importance."""

        # Sort by importance (descending)
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
        """Clean up task memory when task completes."""
        if task_id in self.task_stores:
            self.task_stores[task_id].clear()
            del self.task_stores[task_id]
```

---

## 7. Migration Path

### 7.1 Current State

Current `ContextStore` is a simple dict wrapper:
```python
@dataclass
class ContextStore:
    items: Dict[str, ContextItem] = field(default_factory=dict)
```

### 7.2 Migration Strategy

**Phase 1:** Implement new multi-tier architecture in parallel
**Phase 2:** Update PipelineExecutor to use new ContextAssembler
**Phase 3:** Deprecate old ContextStore
**Phase 4:** Remove old implementation

**Compatibility:** New ContextAssembler can accept old-style adds temporarily

---

## 8. Future Enhancements

### 8.1 Persistent Backends

**File-backed:**
```python
class JSONFileBackend(MemoryBackend):
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.items = self._load()

    def add(self, item: ContextItem):
        self.items[item.context_item_id] = item
        self._save()  # With debouncing
```

**SQLite:**
```python
class SQLiteBackend(MemoryBackend):
    def __init__(self, db_path: Path):
        self.conn = sqlite3.connect(db_path)
        self._create_tables()
```

### 8.2 Vector Search

Add embedding field to ContextItem for semantic retrieval:
```python
def query_semantic(self, query_embedding: List[float], limit: int) -> List[ContextItem]:
    """Query by semantic similarity."""
```

### 8.3 Automatic Paging Policies

Learn optimal budget allocation from telemetry

---

## 9. Testing Strategy

### 9.1 Unit Tests

- Each memory store independently
- Backend implementations (InMemory, future File/SQLite)
- Query filtering and operators
- Eviction policies

### 9.2 Integration Tests

- Multi-tier context assembly
- Budget allocation across tiers
- Task cleanup on completion
- Project isolation

### 9.3 Performance Tests

- Large item counts (1000+ items)
- Query performance
- Memory usage

---

## Success Criteria

✅ Three memory tiers implemented and isolated
✅ Paging policies working (no automatic promotion)
✅ ContextAssembler builds from all three tiers
✅ Project isolation enforced
✅ Task memory automatically cleaned up
✅ Tests pass (unit + integration)
✅ Compatible with existing code via migration path

---

**Design Complete - Ready for Minion Implementation**

Next: Spawn Minions 1-4 for parallel implementation of:
- Minion 1: MemoryBackend interface + InMemoryBackend
- Minion 2: TaskMemoryStore
- Minion 3: ProjectMemoryStore
- Minion 4: GlobalMemoryStore
