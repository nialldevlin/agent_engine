"""Engine error and failure signatures."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional

from pydantic import Field

from .base import SchemaBase, Severity


class FailureCode(str, Enum):
    PLAN_INVALID = "plan_invalid"
    TOOL_FAILURE = "tool_failure"
    JSON_ERROR = "json_error"
    CONTEXT_MISS = "context_miss"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


class EngineErrorCode(str, Enum):
    VALIDATION = "validation"
    ROUTING = "routing"
    TOOL = "tool"
    AGENT = "agent"
    JSON = "json"
    SECURITY = "security"
    UNKNOWN = "unknown"


class EngineErrorSource(str, Enum):
    CONFIG_LOADER = "config_loader"
    RUNTIME = "runtime"
    AGENT_RUNTIME = "agent_runtime"
    TOOL_RUNTIME = "tool_runtime"
    JSON_ENGINE = "json_engine"
    MEMORY = "memory"
    ROUTER = "router"


class FailureSignature(SchemaBase):
    code: FailureCode
    message: str
    stage_id: Optional[str] = Field(default=None)
    severity: Severity = Field(default=Severity.ERROR)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EngineError(SchemaBase):
    error_id: str
    code: EngineErrorCode
    message: str
    source: EngineErrorSource
    severity: Severity = Field(default=Severity.ERROR)
    details: Optional[Dict[str, Any]] = Field(default=None)
    stage_id: Optional[str] = Field(default=None)
    task_id: Optional[str] = Field(default=None)
    timestamp: Optional[str] = Field(default=None)
