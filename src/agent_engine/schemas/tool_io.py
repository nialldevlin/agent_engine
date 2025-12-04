"""Schemas for example tool inputs and outputs used by the basic LLM agent."""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import Field

from .base import SchemaBase


class GatherContextInput(SchemaBase):
    task_id: str
    request: Optional[str] = None
    mode: Optional[str] = None
    context_items: List[Dict] = Field(default_factory=list)


class GatherContextOutput(SchemaBase):
    workspace_files: List[str] = Field(default_factory=list)
    request: Optional[str] = None


class ExecutionInput(SchemaBase):
    task_id: str
    request: Optional[str] = None
    mode: Optional[str] = None
    context_items: List[Dict] = Field(default_factory=list)


class ExecutionOutput(SchemaBase):
    executed: Optional[bool] = None
    kind: Optional[str] = None
    entries: Optional[List[str]] = None
    path: Optional[str] = None
    content: Optional[str] = None
    error: Optional[str] = None
    query: Optional[str] = None
    matches: Optional[List[str]] = None
    message: Optional[str] = None
