"""Event schemas."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional

from pydantic import Field

from .base import SchemaBase


class EventType(str, Enum):
    TASK = "task_started"
    STAGE = "stage_completed"
    AGENT = "agent"
    TOOL = "tool"
    ROUTING = "routing"
    MEMORY = "memory"
    ERROR = "error"
    TELEMETRY = "telemetry"


class Event(SchemaBase):
    event_id: str
    task_id: Optional[str] = Field(default=None)
    stage_id: Optional[str] = Field(default=None)
    type: EventType
    timestamp: Optional[str] = Field(default=None)
    payload: Dict[str, Any]
    metadata: Dict[str, Any] = Field(default_factory=dict)
