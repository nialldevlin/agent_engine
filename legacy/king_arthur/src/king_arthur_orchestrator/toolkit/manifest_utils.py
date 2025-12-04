"""Toolkit entrypoints for manifest and registry helpers."""

from __future__ import annotations

from king_arthur_orchestrator.round_table import (
    AgentDescriptor,
    MANIFESTS_DIR,
    ROYALTY_DIR,
    SQUIRES_DIR,
    PEASANTS_DIR,
    TEMPLATES_DIR,
    MANIFEST_REGISTRY_PATH,
    ROUND_TABLE_DIR,
    load_manifest,
    load_all,
    load_registry,
    select_by_type,
    get_by_name,
    to_descriptor,
    sync_manifest_to_registry,
    remove_from_registry,
    validate_manifest_schema,
    validate_registry_paths,
)
from king_arthur_orchestrator.toolkit.version_utils import (
    compare_versions,
    is_compatible,
    parse_version,
)

__all__ = [
    "AgentDescriptor",
    "MANIFESTS_DIR",
    "ROYALTY_DIR",
    "SQUIRES_DIR",
    "PEASANTS_DIR",
    "TEMPLATES_DIR",
    "MANIFEST_REGISTRY_PATH",
    "ROUND_TABLE_DIR",
    "load_manifest",
    "load_all",
    "load_registry",
    "select_by_type",
    "get_by_name",
    "to_descriptor",
    "parse_version",
    "compare_versions",
    "is_compatible",
    "sync_manifest_to_registry",
    "remove_from_registry",
    "validate_manifest_schema",
    "validate_registry_paths",
]
