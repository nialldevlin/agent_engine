"""Stage schemas."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional

from pydantic import Field

from .base import SchemaBase


class StageType(str, Enum):
    AGENT = "agent"
    TOOL = "tool"
    DECISION = "decision"
    MERGE = "merge"
    TRANSFORM = "transform"


class OnErrorPolicy(str, Enum):
    FAIL = "fail"
    RETRY = "retry"
    SKIP = "skip"
    FALLBACK_STAGE = "fallback_stage"


class Stage(SchemaBase):
    stage_id: str
    name: str
    type: StageType
    entrypoint: bool = Field(default=False)
    terminal: bool = Field(default=False)
    agent_id: Optional[str] = Field(default=None)
    tool_id: Optional[str] = Field(default=None)
    inputs_schema_id: Optional[str] = Field(default=None)
    outputs_schema_id: Optional[str] = Field(default=None)
    on_error: Dict[str, Any] = Field(
        default_factory=lambda: {
            "policy": OnErrorPolicy.FAIL.value,
            "max_retries": None,
            "fallback_stage_id": None,
        }
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)
