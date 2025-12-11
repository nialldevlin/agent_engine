"""Tests for Phase 15: Adapter Metadata Tracking.

Tests adapter schema, collection, and integration with engine metadata.
"""

import pytest
from agent_engine.schemas import AdapterType, AdapterMetadata, EngineMetadata
from agent_engine.adapters import AdapterRegistry, initialize_adapters
from agent_engine.runtime.metadata_collector import (
    collect_adapter_versions,
    collect_adapter_metadata,
    collect_engine_metadata,
)


class TestAdapterType:
    """Tests for AdapterType enum."""

    def test_adapter_type_llm(self):
        """Test LLM adapter type."""
        assert AdapterType.LLM == "llm"
        assert AdapterType.LLM.value == "llm"

    def test_adapter_type_tool(self):
        """Test TOOL adapter type."""
        assert AdapterType.TOOL == "tool"

    def test_adapter_type_memory(self):
        """Test MEMORY adapter type."""
        assert AdapterType.MEMORY == "memory"

    def test_adapter_type_storage(self):
        """Test STORAGE adapter type."""
        assert AdapterType.STORAGE == "storage"

    def test_adapter_type_plugin(self):
        """Test PLUGIN adapter type."""
        assert AdapterType.PLUGIN == "plugin"


class TestAdapterMetadata:
    """Tests for AdapterMetadata dataclass."""

    def test_adapter_metadata_creation(self):
        """Test creating AdapterMetadata instance."""
        metadata = AdapterMetadata(
            adapter_id="openai",
            adapter_type=AdapterType.LLM,
            version="1.0.0",
            config_hash="abc123",
            enabled=True
        )
        assert metadata.adapter_id == "openai"
        assert metadata.adapter_type == AdapterType.LLM
        assert metadata.version == "1.0.0"
        assert metadata.config_hash == "abc123"
        assert metadata.enabled is True

    def test_adapter_metadata_defaults(self):
        """Test AdapterMetadata defaults."""
        metadata = AdapterMetadata(
            adapter_id="tool1",
            adapter_type=AdapterType.TOOL
        )
        assert metadata.adapter_id == "tool1"
        assert metadata.adapter_type == AdapterType.TOOL
        assert metadata.version == ""
        assert metadata.config_hash == ""
        assert metadata.enabled is True
        assert metadata.metadata == {}

    def test_adapter_metadata_with_extra_metadata(self):
        """Test AdapterMetadata with extra metadata dict."""
        extra = {"env": "prod", "region": "us-west"}
        metadata = AdapterMetadata(
            adapter_id="s3-storage",
            adapter_type=AdapterType.STORAGE,
            metadata=extra
        )
        assert metadata.metadata == extra


class TestAdapterRegistry:
    """Tests for AdapterRegistry.get_adapter_metadata()."""

    def test_get_adapter_metadata_empty_registry(self):
        """Test get_adapter_metadata with no adapters."""
        registry = AdapterRegistry()
        metadata_list = registry.get_adapter_metadata()
        assert isinstance(metadata_list, list)
        assert len(metadata_list) == 0

    def test_get_adapter_metadata_with_llm_provider(self):
        """Test get_adapter_metadata with LLM provider."""
        registry = AdapterRegistry()
        registry.register_llm_provider("openai", {"api_key": "sk-..."})
        metadata_list = registry.get_adapter_metadata()

        assert len(metadata_list) == 1
        assert metadata_list[0].adapter_id == "openai"
        assert metadata_list[0].adapter_type == AdapterType.LLM
        assert metadata_list[0].enabled is True

    def test_get_adapter_metadata_with_tool(self):
        """Test get_adapter_metadata with tool."""
        registry = AdapterRegistry()
        registry.register_tool({"id": "search", "name": "Search Tool"})
        metadata_list = registry.get_adapter_metadata()

        assert len(metadata_list) == 1
        assert metadata_list[0].adapter_id == "search"
        assert metadata_list[0].adapter_type == AdapterType.TOOL

    def test_get_adapter_metadata_with_mixed_adapters(self):
        """Test get_adapter_metadata with both LLM and tools."""
        registry = AdapterRegistry()
        registry.register_llm_provider("openai", {})
        registry.register_llm_provider("anthropic", {})
        registry.register_tool({"id": "calculator", "name": "Calc"})
        registry.register_tool({"id": "search", "name": "Search"})

        metadata_list = registry.get_adapter_metadata()
        assert len(metadata_list) == 4

        llm_adapters = [m for m in metadata_list if m.adapter_type == AdapterType.LLM]
        tool_adapters = [m for m in metadata_list if m.adapter_type == AdapterType.TOOL]

        assert len(llm_adapters) == 2
        assert len(tool_adapters) == 2


class TestMetadataCollector:
    """Tests for metadata collection functions."""

    def test_collect_adapter_versions_no_registry(self):
        """Test collect_adapter_versions with None registry."""
        versions = collect_adapter_versions(None)
        assert versions == {}

    def test_collect_adapter_versions_empty_registry(self):
        """Test collect_adapter_versions with empty registry."""
        registry = AdapterRegistry()
        versions = collect_adapter_versions(registry)
        assert versions == {}

    def test_collect_adapter_versions_with_versions(self):
        """Test collect_adapter_versions with version data."""
        registry = AdapterRegistry()
        registry.register_llm_provider("openai", {})
        registry.register_tool({"id": "tool1"})

        # Test that collect_adapter_versions calls get_adapter_metadata correctly
        versions = collect_adapter_versions(registry)
        # Versions will be empty since adapters have no version initially
        assert isinstance(versions, dict)

    def test_collect_adapter_metadata_no_registry(self):
        """Test collect_adapter_metadata with None registry."""
        metadata_list = collect_adapter_metadata(None)
        assert metadata_list == []

    def test_collect_adapter_metadata_empty_registry(self):
        """Test collect_adapter_metadata with empty registry."""
        registry = AdapterRegistry()
        metadata_list = collect_adapter_metadata(registry)
        assert metadata_list == []

    def test_collect_adapter_metadata_with_adapters(self):
        """Test collect_adapter_metadata with registered adapters."""
        registry = AdapterRegistry()
        registry.register_llm_provider("openai", {})
        registry.register_tool({"id": "calculator"})

        metadata_list = collect_adapter_metadata(registry)
        assert len(metadata_list) == 2
        assert all(isinstance(m, AdapterMetadata) for m in metadata_list)

    def test_collect_engine_metadata_includes_adapters(self, tmp_path):
        """Test that collect_engine_metadata includes adapter_metadata."""
        # Create minimal config dir
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        registry = AdapterRegistry()
        registry.register_llm_provider("openai", {})
        registry.register_tool({"id": "search"})

        metadata = collect_engine_metadata(str(config_dir), registry)

        assert isinstance(metadata, EngineMetadata)
        assert isinstance(metadata.adapter_metadata, list)
        assert len(metadata.adapter_metadata) == 2

    def test_engine_metadata_adapter_metadata_field(self, tmp_path):
        """Test that EngineMetadata has adapter_metadata field."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        metadata = EngineMetadata(
            engine_version="1.0.0",
            adapter_metadata=[]
        )
        assert hasattr(metadata, "adapter_metadata")
        assert metadata.adapter_metadata == []


class TestIntegration:
    """Integration tests for adapter metadata tracking."""

    def test_initialize_adapters_with_metadata(self):
        """Test initialize_adapters creates metadata-capable registry."""
        agents = [{"id": "agent1", "llm": "openai"}]
        tools = [{"id": "search"}]

        registry = initialize_adapters(agents, tools)
        metadata_list = registry.get_adapter_metadata()

        assert len(metadata_list) == 2
        llm_found = any(m.adapter_id == "openai" for m in metadata_list)
        tool_found = any(m.adapter_id == "search" for m in metadata_list)

        assert llm_found
        assert tool_found

    def test_adapter_metadata_roundtrip(self):
        """Test creating and retrieving adapter metadata."""
        original = AdapterMetadata(
            adapter_id="test-adapter",
            adapter_type=AdapterType.PLUGIN,
            version="2.1.0",
            config_hash="hash123",
            enabled=False,
            metadata={"key": "value"}
        )

        # Store in list like EngineMetadata would
        engine_metadata = EngineMetadata(
            engine_version="1.0.0",
            adapter_metadata=[original]
        )

        # Retrieve
        retrieved = engine_metadata.adapter_metadata[0]
        assert retrieved.adapter_id == original.adapter_id
        assert retrieved.adapter_type == original.adapter_type
        assert retrieved.version == original.version
        assert retrieved.config_hash == original.config_hash
        assert retrieved.enabled == original.enabled
        assert retrieved.metadata == original.metadata
