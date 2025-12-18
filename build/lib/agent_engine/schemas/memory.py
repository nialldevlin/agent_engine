"""Memory and context schemas."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import Field

from .base import SchemaBase


class MemoryStoreConfig(SchemaBase):
    retention: Optional[str] = Field(default=None)
    max_items: Optional[int] = Field(default=None)
    backend: Optional[str] = Field(default="in_memory", description="Storage backend: 'in_memory', 'jsonl', or 'sqlite'")
    file_path: Optional[str] = Field(default=None, description="Path for JSONL backend")
    db_path: Optional[str] = Field(default=None, description="Path for SQLite backend")


class CompressionPolicy(SchemaBase):
    mode: Optional[str] = Field(default=None, description="cheap | balanced | max_quality")
    compression_ratio_target: Optional[float] = Field(default=None)


class ContextPolicy(SchemaBase):
    head_tail_preserve: Optional[int] = Field(default=None)
    middle_compress: bool = Field(default=True)


class MemoryConfig(SchemaBase):
    memory_config_id: str
    stores: Dict[str, MemoryStoreConfig] = Field(default_factory=dict)
    compression_policy: Optional[CompressionPolicy] = Field(default=None)
    context_policy: Optional[ContextPolicy] = Field(default=None)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ContextProfileSource(SchemaBase):
    """Memory source configuration for context assembly.

    Per AGENT_ENGINE_SPEC §4 and PROJECT_INTEGRATION_SPEC §3.4:

    A ContextProfileSource specifies which memory layer to retrieve from during context assembly,
    and optionally defines filters for selecting specific items within that layer.

    Memory Layers:
    - "task": Task-local memory store (items created within this specific Task).
    - "project": Project-wide memory store (shared across all Tasks in the project).
    - "global": Global-wide memory store (optionally available across projects).

    Context Assembly:
    - The Context Assembler reads from one or more sources defined in the ContextProfile.
    - Items are retrieved according to the profile's retrieval_policy (recency, semantic, hybrid).
    - Items are filtered by tags if specified.
    - Assembled context is read-only and passed to the node.

    Fields:
        store: Memory layer name - one of "task", "project", or "global".
        tags: Optional list of tags to filter items within the memory layer.
              If empty, all items from the layer are candidates for retrieval.
    """
    store: str = Field(..., description="Memory layer: 'task', 'project', or 'global'")
    tags: List[str] = Field(default_factory=list, description="Optional filter tags")


class ContextProfile(SchemaBase):
    """Context assembly profile – defines what memory to retrieve for a node and how.

    Per AGENT_ENGINE_SPEC §4, AGENT_ENGINE_OVERVIEW §1.5, and PROJECT_INTEGRATION_SPEC §3.4:

    A ContextProfile specifies how the Context Assembler should build structured, read-only
    context for nodes. Each node specifies exactly one of: a context profile ID, "global", or "none".
    This ensures clear, deterministic visibility of information during execution.

    Context Assembly Semantics:
    - The Context Assembler runs before each node execution.
    - It retrieves items from memory layers specified in sources.
    - Items are selected and ordered according to retrieval_policy.
    - The token budget (max_tokens) limits the assembled context size.
    - Assembled context is read-only and cannot be modified by nodes.
    - Nodes receive only what is defined by their profile, preventing accidental visibility leaks.

    Retrieval Policies:
    - "recency": Most recent items first (timestamp-based ordering).
    - "semantic": Most relevant by embedding similarity (vector search).
    - "hybrid": Blend of recency and semantic relevance (weighted combination).

    Memory Layers (per ContextProfileSource):
    - "task": Items local to the current Task.
    - "project": Items shared across all Tasks in the project.
    - "global": Items optionally available across projects.

    Context Profile Invariants:
    - Exactly one profile per node (no multi-profile per node).
    - Every node must choose: profile ID, "global", or "none".
    - Profiles must reference valid sources.
    - max_tokens must be a positive integer.
    - retrieval_policy must be one of the defined policies.

    Fields:
        id: Unique profile identifier (referenced by nodes via Node.context field).
        max_tokens: Maximum token budget for assembled context (limits context size).
        retrieval_policy: Retrieval strategy - one of "recency", "semantic", or "hybrid".
        sources: List of ContextProfileSource objects specifying which memory layers to query.
        metadata: Additional profile-specific configuration (e.g., custom policy parameters).
    """
    id: str = Field(..., description="Unique context profile identifier")
    max_tokens: int = Field(..., description="Maximum token budget for assembled context")
    retrieval_policy: str = Field(..., description="Retrieval policy: 'recency', 'semantic', or 'hybrid'")
    sources: List[ContextProfileSource] = Field(..., description="Memory sources to retrieve from")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional profile configuration")


class ContextItem(SchemaBase):
    context_item_id: str
    kind: str
    source: str
    timestamp: Optional[str] = Field(default=None)
    tags: List[str] = Field(default_factory=list)
    importance: Optional[float] = Field(default=None)
    token_cost: Optional[float] = Field(default=None)
    payload: Any
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ContextFingerprint(SchemaBase):
    task_id: str
    files: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    mode: Optional[str] = Field(default=None)
    approx_complexity: Optional[float] = Field(default=None)
    hash: Optional[str] = Field(default=None)


class ContextRequest(SchemaBase):
    context_request_id: str
    budget_tokens: int
    domains: List[str] = Field(default_factory=list)
    history_types: List[str] = Field(default_factory=list)
    mode: Optional[str] = Field(default=None)
    agent_profile: Optional[str] = Field(default=None)


class ContextPackage(SchemaBase):
    context_package_id: str
    items: List[ContextItem] = Field(default_factory=list)
    summary: Optional[str] = Field(default=None)
    compression_ratio: Optional[float] = Field(default=None)
