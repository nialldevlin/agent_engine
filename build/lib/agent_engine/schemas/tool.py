"""Tool schemas."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import Field

from .base import SchemaBase


class ToolKind(str, Enum):
    DETERMINISTIC = "deterministic"
    LLM_TOOL = "llm_tool"


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
    """Tool definition – capabilities, permissions, and metadata for deterministic tools.

    Per AGENT_ENGINE_SPEC §5, AGENT_ENGINE_OVERVIEW §1.4, and PROJECT_INTEGRATION_SPEC §3.3:

    Tools are deterministic helpers that extend node capabilities in a controlled, permission-regulated
    manner. Tools are not nodes and never part of the DAG; they are invoked *within* node operations.
    All tool usage is explicitly configured and logged.

    Two-Level Permission Model:
    Tool permissions operate at two levels:
    1. TOOL LEVEL (ToolDefinition): Defines what a tool CAN do
       - capabilities: List of operations the tool can perform
       - allow_network: Whether the tool may access external networks
       - allow_shell: Whether the tool may execute shell commands
       - filesystem_root: Optional root restriction for filesystem access
       - These are the tool's maximum permitted capabilities.

    2. NODE LEVEL (Node.tools): Defines what a node MAY call
       - Node.tools contains a whitelist of tool IDs
       - A node can only call tools that appear in its whitelist
       - This further restricts tool access per node

    BOTH levels must be satisfied for tool invocation:
    - Tool must declare the capability
    - Node must whitelist the tool
    - Together these enforce least-privilege access

    Tool Status Model:
    - Tools report status using the UniversalStatus model (PENDING, IN_PROGRESS, COMPLETED, FAILED, etc.)
    - Tool failure due to misuse (e.g., permission violation) typically causes node failure
    - Tool errors not caused by misuse are recorded but may not automatically fail the node
    - Tool status propagates upward: tool status → node status → task status

    Fields:
        tool_id: Unique tool identifier (referenced by Node.tools).
        kind: Tool type - DETERMINISTIC or LLM_TOOL.
        name: Human-readable name.
        description: Description of what the tool does.
        inputs_schema_id: Schema ID for tool input validation.
        outputs_schema_id: Schema ID for tool output validation.
        capabilities: List of ToolCapability values (DETERMINISTIC_SAFE, WORKSPACE_MUTATION, etc.).
        allowed_context: List of context types the tool is permitted to access.
        risk_level: Risk rating - LOW, MEDIUM, or HIGH (for audit and policy enforcement).
        version: Semantic version string (default "0.0.1").
        metadata: Additional tool-specific data (e.g., timeout, retry hints).
        allow_network: Whether this tool may access external networks.
        allow_shell: Whether this tool may execute shell commands.
        filesystem_root: Optional root path restricting filesystem access (None = no restriction).
    """

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
    allow_network: bool = Field(default=False, description="Whether tool can access network")
    allow_shell: bool = Field(default=False, description="Whether tool can execute shell commands")
    filesystem_root: Optional[str] = Field(default=None, description="Filesystem access restriction root path")
