"""Workflow graph and pipeline schemas."""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import Field

from .base import SchemaBase


class Edge(SchemaBase):
    from_stage_id: str
    to_stage_id: str
    condition: Optional[str] = Field(default=None, description="Tag or expression")


class WorkflowGraph(SchemaBase):
    workflow_id: str
    stages: List[str] = Field(..., description="List of stage IDs")
    edges: List[Edge] = Field(default_factory=list)
    invariants: Dict[str, bool] = Field(default_factory=dict)


class Pipeline(SchemaBase):
    pipeline_id: str
    name: str
    description: str
    workflow_id: str
    start_stage_ids: List[str]
    end_stage_ids: List[str]
    allowed_modes: List[str] = Field(default_factory=list)
    fallback_end_stage_ids: List[str] = Field(default_factory=list)
    metadata: Dict[str, object] = Field(default_factory=dict)
