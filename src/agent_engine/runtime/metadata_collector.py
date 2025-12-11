"""Metadata collector for Phase 11 Engine Metadata & Versioning Layer.

Collects and records immutable metadata for every engine load and execution,
including engine version, manifest hashes, schema versions, and adapter versions.
"""

import os
import hashlib
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, Optional

from agent_engine import __version__
from agent_engine.schemas import EngineMetadata


def compute_file_hash(file_path: str) -> str:
    """Compute SHA256 hash of a file.

    Args:
        file_path: Path to the file to hash

    Returns:
        Hex string of SHA256 hash, or empty string if file doesn't exist
    """
    if not os.path.exists(file_path):
        return ""

    sha256 = hashlib.sha256()
    try:
        with open(file_path, 'rb') as f:
            # Read in chunks to handle large files
            for chunk in iter(lambda: f.read(4096), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
    except Exception:
        return ""


def collect_manifest_hashes(config_dir: str) -> Dict[str, str]:
    """Collect SHA256 hashes for all manifest files in config directory.

    Computes deterministic SHA256 hashes for all manifest files found
    in the configuration directory.

    Args:
        config_dir: Path to configuration directory

    Returns:
        Dictionary mapping filename to SHA256 hash (empty dict if none found)
    """
    manifest_files = [
        "workflow.yaml",
        "agents.yaml",
        "tools.yaml",
        "memory.yaml",
        "plugins.yaml",
        "schemas.yaml"  # If schemas manifest exists
    ]

    hashes = {}
    for filename in manifest_files:
        file_path = os.path.join(config_dir, filename)
        if os.path.exists(file_path):
            hash_value = compute_file_hash(file_path)
            if hash_value:
                hashes[filename] = hash_value

    return hashes


def collect_adapter_versions(adapter_registry=None) -> Dict[str, str]:
    """Collect versions from registered adapters.

    For Phase 11, this returns empty dict since adapters don't expose versions yet.
    Future phases can enhance adapter registry to track versions.

    Args:
        adapter_registry: AdapterRegistry instance (optional)

    Returns:
        Dictionary mapping adapter name to version string
    """
    # Phase 11: Return empty dict (adapters don't have version metadata yet)
    # Future phases can add version tracking to AdapterRegistry
    return {}


def collect_engine_metadata(
    config_dir: str,
    adapter_registry=None
) -> EngineMetadata:
    """Collect all engine metadata for the current load.

    Gathers comprehensive metadata including engine version, manifest hashes,
    schema version, adapter versions, and timestamp. Metadata is immutable
    once collected.

    Args:
        config_dir: Path to configuration directory
        adapter_registry: Optional adapter registry for version collection

    Returns:
        EngineMetadata instance with all collected metadata

    Raises:
        ValueError: If config_dir doesn't exist or isn't readable
    """
    if not os.path.isdir(config_dir):
        raise ValueError(f"Config directory does not exist: {config_dir}")

    manifest_hashes = collect_manifest_hashes(config_dir)
    adapter_versions = collect_adapter_versions(adapter_registry) if adapter_registry else {}

    metadata = EngineMetadata(
        engine_version=__version__,
        manifest_hashes=manifest_hashes,
        schema_version=__version__,  # Use engine version as schema version
        adapter_versions=adapter_versions,
        load_timestamp=datetime.now(ZoneInfo("UTC")).isoformat(),
        config_dir=config_dir
    )

    return metadata
