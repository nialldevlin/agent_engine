"""Tool schemas."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import Field

from .base import SchemaBase


class ToolKind(str, Enum):
    DETERMINISTIC = "deterministic"
    LLM_PEASANT = "llm_peasant"


class ToolCapability(str, Enum):
    DETERMINISTIC_SAFE = "deterministic_safe"
    WORKSPACE_MUTATION = "workspace_mutation"
    EXTERNAL_NETWORK = "external_network"
    EXPENSIVE = "expensive"


class ToolRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ToolStepKind(str, Enum):
    READ = "read"
    WRITE = "write"
    ANALYZE = "analyze"
    TEST = "test"


class ToolStep(SchemaBase):
    step_id: str
    tool_id: str
    inputs: Any
    reason: Optional[str] = Field(default=None)
    kind: ToolStepKind = Field(default=ToolStepKind.ANALYZE)


class ToolPlan(SchemaBase):
    tool_plan_id: str
    steps: List[ToolStep]


class ToolCallRecord(SchemaBase):
    call_id: str
    tool_id: str
    stage_id: str
    inputs: Any
    output: Optional[Any] = Field(default=None)
    error: Optional[Any] = Field(default=None)
    started_at: Optional[str] = Field(default=None)
    completed_at: Optional[str] = Field(default=None)
    metadata: Dict[str, object] = Field(default_factory=dict)


class ToolDefinition(SchemaBase):
    tool_id: str
    kind: ToolKind
    name: str
    description: str
    inputs_schema_id: str
    outputs_schema_id: str
    capabilities: List[ToolCapability] = Field(default_factory=list)
    allowed_context: List[str] = Field(default_factory=list)
    risk_level: ToolRiskLevel = Field(default=ToolRiskLevel.LOW)
    version: str = Field(default="0.0.1")
    metadata: Dict[str, object] = Field(default_factory=dict)
