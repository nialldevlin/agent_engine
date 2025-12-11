"""Engine metadata schema for Phase 11.

Records immutable metadata (engine version, manifest hashes, schema revisions,
adapter versions) for every load and execution.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class EngineMetadata:
    """Immutable metadata recorded for every engine load and execution.

    This schema captures the engine state at initialization time, including
    versions, manifest hashes, and configuration details. Metadata is immutable
    once collected and used for verification and debugging.
    """

    # Engine version from __version__
    engine_version: str

    # SHA256 hashes of all loaded manifests
    manifest_hashes: Dict[str, str] = field(default_factory=dict)
    # Example: {"workflow.yaml": "abc123...", "agents.yaml": "def456..."}

    # Schema version (currently use engine version)
    schema_version: str = ""

    # Adapter versions from registry
    adapter_versions: Dict[str, str] = field(default_factory=dict)
    # Example: {"openai": "1.0.0", "anthropic": "0.9.1"}

    # Timestamp when metadata was collected (ISO-8601)
    load_timestamp: str = ""

    # Config directory path
    config_dir: str = ""

    # Additional metadata for extensibility
    additional: Dict[str, str] = field(default_factory=dict)
