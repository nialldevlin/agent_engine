"""Common schema utilities and base classes."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict

from pydantic import BaseModel, ConfigDict


class SchemaBase(BaseModel):
    """Base model with common config for Agent Engine schemas."""

    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    def json_schema(self) -> Dict[str, Any]:
        """Return the JSON schema for this model class."""
        return self.model_json_schema()  # pragma: no cover


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
