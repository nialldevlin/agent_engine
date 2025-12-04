"""Memory and context schemas."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import Field

from .base import SchemaBase


class MemoryStoreConfig(SchemaBase):
    retention: Optional[str] = Field(default=None)
    max_items: Optional[int] = Field(default=None)


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
