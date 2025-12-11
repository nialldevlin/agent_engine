"""Artifact schema definitions for Phase 10 Artifact Storage Subsystem."""

from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


class ArtifactType(str, Enum):
    """Types of artifacts that can be stored."""
    NODE_OUTPUT = "node_output"
    TOOL_RESULT = "tool_result"
    TELEMETRY_SNAPSHOT = "telemetry_snapshot"


@dataclass
class ArtifactMetadata:
    """Metadata for a stored artifact."""
    artifact_id: str  # Unique ID (UUID)
    task_id: str
    node_id: Optional[str] = None  # None for telemetry snapshots
    artifact_type: ArtifactType = ArtifactType.NODE_OUTPUT
    timestamp: str = ""  # ISO-8601
    schema_ref: Optional[str] = None  # Schema used for validation
    additional_metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ArtifactRecord:
    """Complete artifact record with metadata and payload."""
    metadata: ArtifactMetadata
    payload: Any  # The actual artifact data
