"""Context assembler with multi-tier memory system."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
import time
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

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
from agent_engine.retrieval import Retriever, OllamaEmbeddingProvider, SimpleVectorStore
from agent_engine.retrieval.retriever import embed_memory_items


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
    workspace_root: Optional[str] = None
    retriever: Optional[Retriever] = None
    rag_index_path: Optional[str] = None
    head_tail_conversation_count: int = 3
    _last_retrieval_metadata: Dict[str, Any] = field(default_factory=dict, init=False)

    def __post_init__(self):
        if self.workspace_root and not self.retriever:
            index_path = self.rag_index_path or os.path.join(
                self.workspace_root, ".agent_engine", "rag_index.json"
            )
            embedder = OllamaEmbeddingProvider()
            store = SimpleVectorStore(index_path)
            self.retriever = Retriever(
                workspace_root=self.workspace_root,
                embedder=embedder,
                store=store,
            )

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

        # Validate retrieval_policy
        valid_policies = ["recency", "semantic", "hybrid"]
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
        self._last_retrieval_metadata = {}
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
        memory_dicts: List[Dict[str, Any]] = []

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
            memory_dicts.extend([self._context_item_to_dict(i) for i in items])

        rag_items: List[ContextItem] = []
        rag_metadata: Dict[str, Any] = {}
        if self._should_use_rag(profile) and self.retriever:
            rag_items, rag_metadata = self._retrieve_semantic_chunks(
                task, profile, memory_dicts
            )
            all_items.extend(rag_items)

        # Sort by recency (timestamp, newest first)
        all_items.sort(key=lambda i: i.timestamp or "", reverse=True)
        protected = self._protected_items(all_items)
        # Select items within token budget with head/tail protection
        selected = self._select_within_token_budget(
            all_items, profile.max_tokens, protected_items=protected
        )

        # Compute compression ratio
        total_cost = sum(i.token_cost or 0 for i in all_items) or 1
        current_cost = sum(i.token_cost or 0 for i in selected)
        compression_ratio = current_cost / total_cost if total_cost > 0 else 1.0

        # Store retrieval metadata for telemetry
        if rag_metadata:
            self._last_retrieval_metadata = rag_metadata

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

    def _should_use_rag(self, profile: ContextProfile) -> bool:
        metadata = profile.metadata or {}
        return bool(metadata.get("rag_enabled") or profile.retrieval_policy in ("semantic", "hybrid"))

    def _resolve_rag_top_k(self, profile: ContextProfile) -> int:
        metadata = profile.metadata or {}
        if "rag_top_k" in metadata:
            return int(metadata.get("rag_top_k") or 5)
        # heuristic: analysts get more context by default
        if "analyst" in profile.id.lower():
            return 8
        return 5

    def _infer_query(self, task: Task) -> str:
        request = getattr(task, "spec", None)
        if request and hasattr(request, "request"):
            req_val = request.request
        else:
            req_val = getattr(task, "current_output", "") or ""
        if isinstance(req_val, str):
            return req_val
        try:
            import json
            return json.dumps(req_val)
        except Exception:
            return str(req_val)

    def _retrieve_semantic_chunks(
        self,
        task: Task,
        profile: ContextProfile,
        memory_items: List[Dict[str, Any]],
    ) -> Tuple[List[ContextItem], Dict[str, Any]]:
        if not self.retriever:
            return [], {}
        query = self._infer_query(task)
        if not query:
            return [], {}

        top_k = self._resolve_rag_top_k(profile)
        start = time.time()
        chunks = self.retriever.search(query, top_k=top_k)
        mem_chunks = []
        if memory_items:
            mem_chunks = embed_memory_items(
                self.retriever.embedder, memory_items, query, top_k=max(1, top_k // 2)
            )
        latency_ms = int((time.time() - start) * 1000)

        all_chunks = chunks + mem_chunks
        rag_items: List[ContextItem] = []
        seen_ids = set()
        for chunk in all_chunks:
            if chunk.chunk_id in seen_ids:
                continue
            seen_ids.add(chunk.chunk_id)
            token_cost = len(chunk.text.split())
            metadata = dict(chunk.metadata)
            metadata["retrieval_score"] = chunk.score
            metadata["source_type"] = metadata.get("source", "file")
            rag_items.append(
                ContextItem(
                    context_item_id=f"rag-{chunk.chunk_id}",
                    kind="retrieval_chunk",
                    source=metadata.get("source_type", "retrieval"),
                    timestamp=None,
                    tags=["retrieval", metadata.get("source_type", "retrieval")],
                    importance=chunk.score,
                    token_cost=token_cost,
                    payload=chunk.text,
                    metadata=metadata,
                )
            )

        rag_metadata = {
            "rag_enabled": True,
            "query": query,
            "top_k": top_k,
            "retrieval_latency_ms": latency_ms,
            "results": [
                {
                    "source_path": c.metadata.get("path") or c.metadata.get("memory_id"),
                    "start_line": c.metadata.get("start_line"),
                    "end_line": c.metadata.get("end_line"),
                    "score": c.score,
                }
                for c in all_chunks
            ],
        }
        return rag_items, rag_metadata

    def _protected_items(self, items: List[ContextItem]) -> List[ContextItem]:
        """Protect system prompt + last N conversation turns from displacement."""
        protected: List[ContextItem] = []
        # System prompt
        for item in items:
            role = item.metadata.get("role") if hasattr(item, "metadata") else None
            if role == "system":
                protected.append(item)
        # Last conversation turns
        convo = [i for i in items if i.metadata.get("role") in ("user", "assistant")]
        convo_sorted = sorted(convo, key=lambda i: i.timestamp or "")
        protected.extend(convo_sorted[-self.head_tail_conversation_count :])

        # Deduplicate by context_item_id
        deduped = {}
        for item in protected:
            deduped[item.context_item_id] = item
        return list(deduped.values())

    def _context_item_to_dict(self, item: ContextItem) -> Dict[str, Any]:
        return {
            "context_item_id": item.context_item_id,
            "kind": item.kind,
            "source": item.source,
            "timestamp": item.timestamp,
            "tags": item.tags,
            "importance": item.importance,
            "token_cost": item.token_cost,
            "payload": item.payload,
            "metadata": item.metadata,
        }

    def _select_within_token_budget(
        self, items: List[ContextItem], budget: int, protected_items: Optional[List[ContextItem]] = None
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
        protected_items = protected_items or []
        protected_ids = {i.context_item_id for i in protected_items}
        selected = []
        current_tokens = 0
        for item in protected_items:
            selected.append(item)
            current_tokens += item.token_cost or 0

        # Sort by importance (descending) then timestamp
        items_sorted = sorted(
            [i for i in items if i.context_item_id not in protected_ids],
            key=lambda i: (-(i.importance or 0), i.timestamp or "")
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

        if self._last_retrieval_metadata:
            metadata['retrieval'] = self._last_retrieval_metadata

        return metadata
