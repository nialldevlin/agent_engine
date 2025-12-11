"""Adapter metadata schema for Phase 15.

Tracks adapter types and metadata for engine configuration tracking.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional


class AdapterType(str, Enum):
    """Types of adapters supported by the engine."""
    LLM = "llm"
    TOOL = "tool"
    MEMORY = "memory"
    STORAGE = "storage"
    PLUGIN = "plugin"


@dataclass
class AdapterMetadata:
    """Metadata for a registered adapter.

    Tracks name, type, version, and configuration details
    for every adapter registered with the engine.
    """

    # Unique identifier for the adapter
    adapter_id: str

    # Type of adapter (llm, tool, memory, storage, plugin)
    adapter_type: AdapterType

    # Version string of the adapter
    version: str = ""

    # Configuration hash for change detection
    config_hash: str = ""

    # Whether the adapter is enabled
    enabled: bool = True

    # Additional metadata for extensibility
    metadata: Dict[str, str] = field(default_factory=dict)
