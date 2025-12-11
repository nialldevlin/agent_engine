"""Context assembler with multi-tier memory system."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from agent_engine.schemas import (
    ContextItem,
    ContextPackage,
    ContextProfile,
    ContextRequest,
    Task,
    MemoryConfig,
)
from agent_engine.runtime.memory import (
    TaskMemoryStore,
    ProjectMemoryStore,
    GlobalMemoryStore,
    InMemoryBackend,
)


@dataclass
class ContextAssembler:
    """Assembles context from multi-tier memory stores.

    Three-tier architecture:
    - Task Memory: Ephemeral, task-scoped (cleared on completion)
    - Project Memory: Persistent, project-scoped (isolated by project_id)
    - Global Memory: Persistent, cross-project (user preferences)

    Legacy ContextStore support has been removed; only multi-tier stores are supported.
    """

    # Multi-tier memory stores
    task_stores: Dict[str, TaskMemoryStore] = field(default_factory=dict)
    project_stores: Dict[str, ProjectMemoryStore] = field(default_factory=dict)
    global_store: GlobalMemoryStore = field(default_factory=lambda: GlobalMemoryStore(
        backend=InMemoryBackend()
    ))

    memory_config: Optional[MemoryConfig] = None
    context_profiles: Dict[str, ContextProfile] = field(default_factory=dict)

    def resolve_context_profile(
        self, context_spec: Optional[str], profiles: Optional[Dict[str, ContextProfile]] = None
    ) -> Optional[ContextProfile]:
        """Resolve context profile from specification.

        Per AGENT_ENGINE_SPEC §4, each node specifies exactly one of:
        - context profile ID (referenced in profiles dict)
        - "global" (built-in global profile)
        - "none" (no context)

        Args:
            context_spec: The context specification (profile ID, "global", or "none")
            profiles: Optional profiles dict to override self.context_profiles

        Returns:
            ContextProfile if context_spec is "global" or valid profile ID, None if "none"

        Raises:
            ValueError: If profile ID not found or retrieval_policy invalid
        """
        if context_spec is None or context_spec == "none":
            return None

        if context_spec == "global":
            # Return built-in global profile
            from agent_engine.schemas import ContextProfileSource
            return ContextProfile(
                id="global_default",
                max_tokens=8000,
                retrieval_policy="recency",
                sources=[
                    ContextProfileSource(store="task", tags=[]),
                    ContextProfileSource(store="project", tags=[]),
                    ContextProfileSource(store="global", tags=[]),
                ],
            )

        # Look up profile by ID
        profile_dict = profiles if profiles is not None else self.context_profiles
        if context_spec not in profile_dict:
            raise ValueError(
                f"Context profile '{context_spec}' not found in available profiles: "
                f"{list(profile_dict.keys())}"
            )

        profile = profile_dict[context_spec]
        self._validate_context_profile(profile)
        return profile

    def _validate_context_profile(self, profile: ContextProfile) -> None:
        """Validate context profile per canonical constraints.

        Args:
            profile: Profile to validate

        Raises:
            ValueError: If profile violates constraints
        """
        # Validate max_tokens
        if profile.max_tokens <= 0:
            raise ValueError(
                f"Context profile '{profile.id}': max_tokens must be > 0, got {profile.max_tokens}"
            )

        # Validate retrieval_policy (v1 only supports recency)
        valid_policies = ["recency"]  # v1 only, semantic/hybrid in future
        if profile.retrieval_policy not in valid_policies:
            raise ValueError(
                f"Context profile '{profile.id}': retrieval_policy '{profile.retrieval_policy}' "
                f"not supported in v1. Supported: {valid_policies}"
            )

        # Validate sources
        valid_stores = {"task", "project", "global"}
        for source in profile.sources:
            if source.store not in valid_stores:
                raise ValueError(
                    f"Context profile '{profile.id}': source store '{source.store}' "
                    f"invalid. Valid stores: {valid_stores}"
                )

    def build_context_for_profile(
        self, task: Task, profile: ContextProfile
    ) -> ContextPackage:
        """Build context package using a specific profile.

        Per AGENT_ENGINE_SPEC §4, this applies the profile's retrieval policy
        to assemble deterministic, read-only context from specified memory sources.

        Args:
            task: Task to build context for
            profile: Context profile specifying sources and budget

        Returns:
            ContextPackage with assembled context items

        Raises:
            ValueError: If memory stores not accessible
        """
        # Get or create memory stores for this task/project
        task_store = self.task_stores.get(task.task_id)
        if not task_store:
            task_store = TaskMemoryStore(task_id=task.task_id)
            self.task_stores[task.task_id] = task_store

        project_id = task.spec.metadata.get("project_id", "default")
        project_store = self.project_stores.get(project_id)
        if not project_store:
            project_store = ProjectMemoryStore(
                project_id=project_id, backend=InMemoryBackend()
            )
            self.project_stores[project_id] = project_store

        # Collect items from specified sources per profile
        all_items: List[ContextItem] = []

        for source in profile.sources:
            if source.store == "task":
                items = task_store.backend.list_all()
            elif source.store == "project":
                items = project_store.backend.list_all()
            elif source.store == "global":
                items = self.global_store.backend.list_all()
            else:
                continue  # Skip unknown stores

            # Apply tag filtering if specified
            if source.tags:
                items = self._filter_items_by_tags(items, source.tags)

            all_items.extend(items)

        # Sort by recency (timestamp, newest first)
        all_items.sort(
            key=lambda i: i.timestamp or "", reverse=True
        )

        # Select items within token budget
        selected = self._select_within_token_budget(all_items, profile.max_tokens)

        # Compute compression ratio
        total_cost = sum(i.token_cost or 0 for i in all_items) or 1
        current_cost = sum(i.token_cost or 0 for i in selected)
        compression_ratio = current_cost / total_cost if total_cost > 0 else 1.0

        return ContextPackage(
            context_package_id=f"ctx-{task.task_id}-{profile.id}",
            items=selected,
            summary=None,
            compression_ratio=compression_ratio,
        )

    def _filter_items_by_tags(
        self, items: List[ContextItem], tags: List[str]
    ) -> List[ContextItem]:
        """Filter items by tag membership.

        Args:
            items: Items to filter
            tags: Tags to match (OR logic: item must have any of these tags)

        Returns:
            Items matching any of the specified tags
        """
        if not tags:
            return items

        filtered = []
        for item in items:
            if any(tag in item.tags for tag in tags):
                filtered.append(item)
        return filtered

    def _select_within_token_budget(
        self, items: List[ContextItem], budget: int
    ) -> List[ContextItem]:
        """Select items within token budget.

        Uses importance-based selection: items are sorted by importance (descending)
        and selected in order until budget is exhausted.

        Args:
            items: Items to select from (should be pre-sorted by recency)
            budget: Maximum tokens to use

        Returns:
            Selected items within budget
        """
        # Sort by importance (descending) then timestamp
        items_sorted = sorted(
            items, key=lambda i: (-(i.importance or 0), i.timestamp or "")
        )

        # Apply HEAD/TAIL compression if configured
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

    def build_context(self, task: Task, request: ContextRequest) -> ContextPackage:
        """Build context package from all memory tiers.

        Process:
        1. Get or create task memory store
        2. Get or create project memory store (from task metadata)
        3. Query all three tiers (task/project/global)
        4. Allocate budget across tiers
        5. Select items within budget using HEAD/TAIL + importance
        6. Return ContextPackage with compression ratio

        """

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

    def get_context_metadata(self, context_package) -> Dict[str, Any]:
        """Extract context metadata for history recording.

        Args:
            context_package: Assembled context package

        Returns:
            Metadata dict with context information
        """
        from typing import Any as TypingAny

        metadata = {}

        if hasattr(context_package, 'items'):
            metadata['items_count'] = len(context_package.items)
            metadata['total_tokens'] = sum(
                getattr(item, 'token_cost', 0) for item in context_package.items
            )

        if hasattr(context_package, 'profile_id'):
            metadata['profile_id'] = context_package.profile_id

        return metadata
