"""Tests for Phase 11: Engine Metadata & Versioning Layer.

Tests the metadata schema, collector, and integration with Engine, Router,
and NodeExecutor.
"""

import os
import pytest
import tempfile
from pathlib import Path

from agent_engine import __version__
from agent_engine.schemas import EngineMetadata
from agent_engine.runtime.metadata_collector import (
    compute_file_hash,
    collect_manifest_hashes,
    collect_adapter_versions,
    collect_engine_metadata,
)


# ============================================================================
# Schema Tests (3 tests)
# ============================================================================

class TestEngineMetadataSchema:
    """Test EngineMetadata schema creation and properties."""

    def test_engine_metadata_creation_with_all_fields(self):
        """Test EngineMetadata creation with all fields populated."""
        metadata = EngineMetadata(
            engine_version="0.0.1",
            manifest_hashes={"workflow.yaml": "abc123", "agents.yaml": "def456"},
            schema_version="0.0.1",
            adapter_versions={"openai": "1.0.0"},
            load_timestamp="2025-01-01T00:00:00+00:00",
            config_dir="/path/to/config"
        )

        assert metadata.engine_version == "0.0.1"
        assert metadata.manifest_hashes == {"workflow.yaml": "abc123", "agents.yaml": "def456"}
        assert metadata.schema_version == "0.0.1"
        assert metadata.adapter_versions == {"openai": "1.0.0"}
        assert metadata.load_timestamp == "2025-01-01T00:00:00+00:00"
        assert metadata.config_dir == "/path/to/config"

    def test_engine_metadata_with_empty_optional_fields(self):
        """Test EngineMetadata with minimal required fields."""
        metadata = EngineMetadata(engine_version="0.0.1")

        assert metadata.engine_version == "0.0.1"
        assert metadata.manifest_hashes == {}
        assert metadata.schema_version == ""
        assert metadata.adapter_versions == {}
        assert metadata.load_timestamp == ""
        assert metadata.config_dir == ""
        assert metadata.additional == {}

    def test_engine_metadata_immutability_fields(self):
        """Test that EngineMetadata has all expected fields."""
        metadata = EngineMetadata(
            engine_version="0.0.1",
            manifest_hashes={"test.yaml": "hash123"}
        )

        # Verify all fields exist
        assert hasattr(metadata, "engine_version")
        assert hasattr(metadata, "manifest_hashes")
        assert hasattr(metadata, "schema_version")
        assert hasattr(metadata, "adapter_versions")
        assert hasattr(metadata, "load_timestamp")
        assert hasattr(metadata, "config_dir")
        assert hasattr(metadata, "additional")


# ============================================================================
# Collector Tests (8 tests)
# ============================================================================

class TestMetadataCollector:
    """Test metadata collection functions."""

    def test_compute_file_hash_with_valid_file(self):
        """Test SHA256 hash computation on a real file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("test content")
            temp_path = f.name

        try:
            hash_val = compute_file_hash(temp_path)

            # Verify it's a valid SHA256 hex string (64 chars)
            assert len(hash_val) == 64
            assert all(c in '0123456789abcdef' for c in hash_val)

            # Verify consistency: same file, same hash
            hash_val2 = compute_file_hash(temp_path)
            assert hash_val == hash_val2
        finally:
            os.unlink(temp_path)

    def test_compute_file_hash_with_nonexistent_file(self):
        """Test SHA256 hash computation returns empty string for missing file."""
        hash_val = compute_file_hash("/nonexistent/file/path.yaml")
        assert hash_val == ""

    def test_compute_file_hash_deterministic(self):
        """Test that hash is deterministic for same file content."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("deterministic content")
            temp_path = f.name

        try:
            hash1 = compute_file_hash(temp_path)
            hash2 = compute_file_hash(temp_path)
            assert hash1 == hash2
        finally:
            os.unlink(temp_path)

    def test_collect_manifest_hashes_with_all_manifests(self):
        """Test manifest hash collection with all manifest files present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create manifest files
            manifest_files = ["workflow.yaml", "agents.yaml", "tools.yaml"]
            for manifest in manifest_files:
                with open(os.path.join(tmpdir, manifest), 'w') as f:
                    f.write(f"content of {manifest}")

            hashes = collect_manifest_hashes(tmpdir)

            # Verify all files are hashed
            assert "workflow.yaml" in hashes
            assert "agents.yaml" in hashes
            assert "tools.yaml" in hashes

            # Verify hashes are valid SHA256
            for filename, hash_val in hashes.items():
                assert len(hash_val) == 64
                assert all(c in '0123456789abcdef' for c in hash_val)

    def test_collect_manifest_hashes_with_missing_optional_manifests(self):
        """Test manifest collection when only required files exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create only workflow and agents
            with open(os.path.join(tmpdir, "workflow.yaml"), 'w') as f:
                f.write("workflow")
            with open(os.path.join(tmpdir, "agents.yaml"), 'w') as f:
                f.write("agents")

            hashes = collect_manifest_hashes(tmpdir)

            # Should have hashes for existing files
            assert "workflow.yaml" in hashes
            assert "agents.yaml" in hashes
            # Should not have hashes for missing optional files
            assert "plugins.yaml" not in hashes
            assert "memory.yaml" not in hashes

    def test_collect_manifest_hashes_empty_directory(self):
        """Test manifest collection on empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hashes = collect_manifest_hashes(tmpdir)
            assert hashes == {}

    def test_collect_adapter_versions_returns_empty_dict(self):
        """Test that adapter version collection returns empty dict in Phase 11."""
        versions = collect_adapter_versions(None)
        assert versions == {}

    def test_collect_engine_metadata_includes_engine_version(self):
        """Test that collected metadata includes correct engine version."""
        with tempfile.TemporaryDirectory() as tmpdir:
            metadata = collect_engine_metadata(tmpdir)

            assert metadata.engine_version == __version__

    def test_collect_engine_metadata_includes_manifest_hashes(self):
        """Test that collected metadata includes manifest hashes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test manifest
            with open(os.path.join(tmpdir, "workflow.yaml"), 'w') as f:
                f.write("test")

            metadata = collect_engine_metadata(tmpdir)

            assert metadata.manifest_hashes is not None
            assert "workflow.yaml" in metadata.manifest_hashes

    def test_collect_engine_metadata_includes_timestamp(self):
        """Test that collected metadata includes ISO-8601 timestamp."""
        with tempfile.TemporaryDirectory() as tmpdir:
            metadata = collect_engine_metadata(tmpdir)

            assert metadata.load_timestamp != ""
            # Verify ISO-8601 format
            assert "T" in metadata.load_timestamp
            assert "+" in metadata.load_timestamp or "Z" in metadata.load_timestamp

    def test_collect_engine_metadata_includes_config_dir(self):
        """Test that collected metadata includes config directory path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            metadata = collect_engine_metadata(tmpdir)

            assert metadata.config_dir == tmpdir

    def test_collect_engine_metadata_schema_version_matches_engine_version(self):
        """Test that schema version matches engine version."""
        with tempfile.TemporaryDirectory() as tmpdir:
            metadata = collect_engine_metadata(tmpdir)

            assert metadata.schema_version == metadata.engine_version
            assert metadata.schema_version == __version__

    def test_collect_engine_metadata_invalid_config_dir(self):
        """Test that collect_engine_metadata raises on invalid config directory."""
        with pytest.raises(ValueError):
            collect_engine_metadata("/nonexistent/directory/path")


# ============================================================================
# Integration Tests (9+ tests)
# ============================================================================

class TestEngineMetadataIntegration:
    """Test metadata integration with Engine, Router, and NodeExecutor."""

    def test_engine_has_metadata_attribute(self):
        """Test that Engine has metadata attribute after initialization."""
        from agent_engine import Engine
        from agent_engine.dag import DAG

        # Create a minimal engine with metadata
        metadata = EngineMetadata(engine_version=__version__)

        engine = Engine(
            config_dir="/tmp",
            workflow=DAG(nodes=[], edges=[]),
            agents=[],
            tools=[],
            schemas={},
            memory_stores={},
            context_profiles={},
            adapters=None,
            plugins=[],
            metadata=metadata
        )

        assert engine.metadata == metadata

    def test_engine_get_metadata_returns_metadata(self):
        """Test that Engine.get_metadata() returns the stored metadata."""
        from agent_engine import Engine
        from agent_engine.dag import DAG

        metadata = EngineMetadata(
            engine_version=__version__,
            config_dir="/tmp"
        )

        engine = Engine(
            config_dir="/tmp",
            workflow=DAG(nodes=[], edges=[]),
            agents=[],
            tools=[],
            schemas={},
            memory_stores={},
            context_profiles={},
            adapters=None,
            plugins=[],
            metadata=metadata
        )

        retrieved_metadata = engine.get_metadata()
        assert retrieved_metadata == metadata
        assert retrieved_metadata.engine_version == __version__

    def test_engine_get_metadata_returns_none_when_not_set(self):
        """Test that Engine.get_metadata() returns None if not initialized."""
        from agent_engine import Engine
        from agent_engine.dag import DAG

        engine = Engine(
            config_dir="/tmp",
            workflow=DAG(nodes=[], edges=[]),
            agents=[],
            tools=[],
            schemas={},
            memory_stores={},
            context_profiles={},
            adapters=None,
            plugins=[]
        )

        # Metadata was not passed, so should be None
        assert engine.get_metadata() is None

    def test_router_receives_metadata(self):
        """Test that Router receives and stores metadata."""
        from agent_engine.runtime.router import Router
        from agent_engine.runtime.task_manager import TaskManager
        from agent_engine.dag import DAG

        metadata = EngineMetadata(engine_version=__version__)
        router = Router(
            dag=DAG(nodes=[], edges=[]),
            task_manager=TaskManager(),
            node_executor=None,
            metadata=metadata
        )

        assert router.metadata == metadata

    def test_router_accepts_none_metadata(self):
        """Test that Router works with metadata=None."""
        from agent_engine.runtime.router import Router
        from agent_engine.runtime.task_manager import TaskManager
        from agent_engine.dag import DAG

        router = Router(
            dag=DAG(nodes=[], edges=[]),
            task_manager=TaskManager(),
            node_executor=None,
            metadata=None
        )

        assert router.metadata is None

    def test_node_executor_receives_metadata(self):
        """Test that NodeExecutor receives and stores metadata."""
        from agent_engine.runtime.node_executor import NodeExecutor

        metadata = EngineMetadata(engine_version=__version__)
        executor = NodeExecutor(
            agent_runtime=None,
            tool_runtime=None,
            context_assembler=None,
            json_engine=None,
            deterministic_registry=None,
            metadata=metadata
        )

        assert executor.metadata == metadata

    def test_node_executor_accepts_none_metadata(self):
        """Test that NodeExecutor works with metadata=None."""
        from agent_engine.runtime.node_executor import NodeExecutor

        executor = NodeExecutor(
            agent_runtime=None,
            tool_runtime=None,
            context_assembler=None,
            json_engine=None,
            deterministic_registry=None,
            metadata=None
        )

        assert executor.metadata is None

    def test_metadata_serialization(self):
        """Test that EngineMetadata can be converted to dict."""
        metadata = EngineMetadata(
            engine_version="0.0.1",
            manifest_hashes={"workflow.yaml": "abc123"},
            schema_version="0.0.1",
            config_dir="/tmp"
        )

        # Should be able to convert to dict via __dict__
        metadata_dict = metadata.__dict__

        assert metadata_dict["engine_version"] == "0.0.1"
        assert metadata_dict["manifest_hashes"] == {"workflow.yaml": "abc123"}

    def test_collect_engine_metadata_includes_all_fields(self):
        """Test that collect_engine_metadata returns complete metadata."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a manifest file
            with open(os.path.join(tmpdir, "workflow.yaml"), 'w') as f:
                f.write("test")

            metadata = collect_engine_metadata(tmpdir)

            # All fields should be populated
            assert metadata.engine_version == __version__
            assert isinstance(metadata.manifest_hashes, dict)
            assert metadata.schema_version == __version__
            assert isinstance(metadata.adapter_versions, dict)
            assert metadata.load_timestamp != ""
            assert metadata.config_dir == tmpdir
            assert isinstance(metadata.additional, dict)

    def test_metadata_immutability_concept(self):
        """Test that metadata fields are properly initialized as immutable structures."""
        metadata = EngineMetadata(engine_version="0.0.1")

        # Fields should be accessible and contain proper defaults
        manifest_hashes_initial = metadata.manifest_hashes
        assert manifest_hashes_initial == {}

        # Verify each field type
        assert isinstance(metadata.manifest_hashes, dict)
        assert isinstance(metadata.adapter_versions, dict)
        assert isinstance(metadata.additional, dict)


# ============================================================================
# Large File Hash Tests
# ============================================================================

class TestLargeFileHashing:
    """Test hashing of large files to verify chunked reading."""

    def test_compute_file_hash_large_file(self):
        """Test SHA256 computation on a file larger than buffer size."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            # Write more than 4096 bytes to test chunking
            content = "x" * 10000
            f.write(content)
            temp_path = f.name

        try:
            hash_val = compute_file_hash(temp_path)

            # Should be valid SHA256
            assert len(hash_val) == 64
            assert all(c in '0123456789abcdef' for c in hash_val)
        finally:
            os.unlink(temp_path)

    def test_compute_file_hash_binary_file(self):
        """Test SHA256 computation on binary file."""
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
            # Write binary content
            f.write(b'\x00\x01\x02\x03' * 1000)
            temp_path = f.name

        try:
            hash_val = compute_file_hash(temp_path)

            # Should be valid SHA256
            assert len(hash_val) == 64
            assert all(c in '0123456789abcdef' for c in hash_val)
        finally:
            os.unlink(temp_path)
