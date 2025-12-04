"""Override schemas."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional

from pydantic import Field

from .base import SchemaBase


class OverrideKind(str, Enum):
    MEMORY = "memory"
    ROUTING = "routing"
    SAFETY = "safety"
    VERBOSITY = "verbosity"
    MODE = "mode"


class OverrideScope(str, Enum):
    TASK = "task"
    PROJECT = "project"
    GLOBAL = "global"


class OverrideSeverity(str, Enum):
    HINT = "hint"
    ENFORCE = "enforce"


class OverrideSpec(SchemaBase):
    override_id: str
    kind: OverrideKind
    scope: OverrideScope
    target: Optional[str] = Field(default=None)
    severity: OverrideSeverity = Field(default=OverrideSeverity.HINT)
    payload: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
