"""Agent schemas."""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from pydantic import Field

from .base import SchemaBase


class AgentRole(str, Enum):
    """Neutral agent roles for manifest-driven configuration."""

    AGENT = "agent"


class ToolBias(str, Enum):
    PREFER_TOOLS = "prefer_tools"
    PREFER_TEXT = "prefer_text"
    BALANCED = "balanced"


class Verbosity(str, Enum):
    TERSE = "terse"
    NORMAL = "normal"
    VERBOSE = "verbose"


class Emphasis(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AgentManifest(SchemaBase):
    reasoning_steps: Optional[int] = Field(default=None)
    tool_bias: ToolBias = Field(default=ToolBias.BALANCED)
    verbosity: Verbosity = Field(default=Verbosity.NORMAL)
    tests_emphasis: Emphasis = Field(default=Emphasis.MEDIUM)


class AgentDefinition(SchemaBase):
    agent_id: str
    role: AgentRole
    profile: Dict[str, object] = Field(default_factory=dict)
    manifest: AgentManifest = Field(default_factory=AgentManifest)
    schema_id: Optional[str] = Field(default=None, description="Expected output schema")
    version: str = Field(default="0.0.1")
    metadata: Dict[str, object] = Field(default_factory=dict)
