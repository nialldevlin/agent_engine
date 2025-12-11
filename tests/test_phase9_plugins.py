"""Phase 9 Plugin System Tests."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from copy import deepcopy

from agent_engine.schemas import Event, EventType, PluginBase, PluginConfig
from agent_engine.plugin_loader import PluginLoader
from agent_engine.plugin_registry import PluginRegistry
from agent_engine.telemetry import TelemetryBus


class MockPlugin(PluginBase):
    """Mock plugin for testing."""

    def __init__(self, plugin_id: str, config: dict = None):
        super().__init__(plugin_id, config)
        self.events_received = []
        self.startup_called = False
        self.shutdown_called = False

    def on_startup(self) -> None:
        self.startup_called = True

    def on_event(self, event: Event) -> None:
        self.events_received.append(event)

    def on_shutdown(self) -> None:
        self.shutdown_called = True


class ErrorPlugin(PluginBase):
    """Plugin that raises errors."""

    def __init__(self, plugin_id: str, config: dict = None):
        super().__init__(plugin_id, config)
        self.error_on_startup = False
        self.error_on_event = False
        self.error_on_shutdown = False

    def on_startup(self) -> None:
        if self.error_on_startup:
            raise RuntimeError("Startup error")

    def on_event(self, event: Event) -> None:
        if self.error_on_event:
            raise RuntimeError("Event error")

    def on_shutdown(self) -> None:
        if self.error_on_shutdown:
            raise RuntimeError("Shutdown error")


# ============================================================================
# SECTION 1: Plugin Schema Tests (PluginConfig)
# ============================================================================


class TestPluginConfig:
    """Tests for PluginConfig schema."""

    def test_plugin_config_creation(self):
        """Test creating a valid PluginConfig."""
        config = PluginConfig(
            id="test_plugin", module="my.plugins.TestPlugin", enabled=True, config={}
        )
        assert config.id == "test_plugin"
        assert config.module == "my.plugins.TestPlugin"
        assert config.enabled is True
        assert config.config == {}

    def test_plugin_config_default_values(self):
        """Test PluginConfig defaults."""
        config = PluginConfig(id="test", module="my.plugins.Test")
        assert config.enabled is True
        assert config.config == {}

    def test_plugin_config_with_custom_config(self):
        """Test PluginConfig with custom config dict."""
        custom_config = {"log_level": "DEBUG", "buffer_size": 100}
        config = PluginConfig(
            id="test", module="my.plugins.Test", config=custom_config
        )
        assert config.config == custom_config

    def test_plugin_config_validate_missing_id(self):
        """Test validation fails with missing id."""
        config = PluginConfig(id="", module="my.plugins.Test")
        with pytest.raises(ValueError, match="Plugin id required"):
            config.validate()

    def test_plugin_config_validate_invalid_id_type(self):
        """Test validation fails with non-string id."""
        config = PluginConfig(id=123, module="my.plugins.Test")
        with pytest.raises(ValueError, match="Plugin id required"):
            config.validate()

    def test_plugin_config_validate_missing_module(self):
        """Test validation fails with missing module."""
        config = PluginConfig(id="test", module="")
        with pytest.raises(ValueError, match="Plugin module required"):
            config.validate()

    def test_plugin_config_validate_invalid_enabled(self):
        """Test validation fails with non-boolean enabled."""
        config = PluginConfig(
            id="test", module="my.plugins.Test", enabled="yes"  # type: ignore
        )
        with pytest.raises(ValueError, match="Plugin enabled must be boolean"):
            config.validate()

    def test_plugin_config_validate_invalid_config(self):
        """Test validation fails with non-dict config."""
        config = PluginConfig(
            id="test", module="my.plugins.Test", config="invalid"  # type: ignore
        )
        with pytest.raises(ValueError, match="Plugin config must be dict"):
            config.validate()


# ============================================================================
# SECTION 2: Plugin Loader Tests
# ============================================================================


class TestPluginLoader:
    """Tests for PluginLoader."""

    def test_load_empty_plugins_yaml(self, tmp_path):
        """Test loading plugins.yaml with empty plugins list."""
        plugins_yaml = tmp_path / "plugins.yaml"
        plugins_yaml.write_text("plugins: []")

        loader = PluginLoader()
        plugins = loader.load_plugins_from_yaml(plugins_yaml)
        assert plugins == []

    def test_load_plugins_yaml_not_exists(self, tmp_path):
        """Test loading non-existent plugins.yaml returns empty list."""
        plugins_yaml = tmp_path / "plugins.yaml"

        loader = PluginLoader()
        plugins = loader.load_plugins_from_yaml(plugins_yaml)
        assert plugins == []

    def test_load_plugins_yaml_invalid_format(self, tmp_path):
        """Test loading invalid YAML raises error."""
        plugins_yaml = tmp_path / "plugins.yaml"
        plugins_yaml.write_text("{ invalid: yaml: content [")

        loader = PluginLoader()
        with pytest.raises(ValueError, match="Failed to load plugins.yaml"):
            loader.load_plugins_from_yaml(plugins_yaml)

    def test_load_single_plugin_with_mock(self, tmp_path):
        """Test loading plugin with mocked import."""
        plugins_yaml = tmp_path / "plugins.yaml"
        plugins_yaml.write_text(
            """
plugins:
  - id: test_plugin
    module: test_module.MockPlugin
    enabled: true
    config: {}
"""
        )

        loader = PluginLoader()

        # Mock the import with real plugin class
        mock_module = MagicMock()
        mock_module.MockPlugin = MockPlugin

        with patch("importlib.import_module", return_value=mock_module):
            plugins = loader.load_plugins_from_yaml(plugins_yaml)
            assert len(plugins) == 1
            assert isinstance(plugins[0], MockPlugin)

    def test_load_disabled_plugin_skipped(self, tmp_path):
        """Test disabled plugins are skipped."""
        plugins_yaml = tmp_path / "plugins.yaml"
        plugins_yaml.write_text(
            """
plugins:
  - id: disabled_plugin
    module: test_module.Plugin
    enabled: false
"""
        )

        loader = PluginLoader()

        # Mock import
        mock_module = MagicMock()
        with patch("importlib.import_module", return_value=mock_module):
            plugins = loader.load_plugins_from_yaml(plugins_yaml)
            assert len(plugins) == 0

    def test_load_plugin_module_not_found(self, tmp_path):
        """Test error when plugin module not found."""
        plugins_yaml = tmp_path / "plugins.yaml"
        plugins_yaml.write_text(
            """
plugins:
  - id: bad_plugin
    module: nonexistent.module.Plugin
"""
        )

        loader = PluginLoader()

        with patch(
            "importlib.import_module", side_effect=ImportError("No module")
        ):
            with pytest.raises(ValueError, match="Cannot import plugin module"):
                loader.load_plugins_from_yaml(plugins_yaml)

    def test_load_plugin_class_not_found(self, tmp_path):
        """Test error when plugin class not found in module."""
        plugins_yaml = tmp_path / "plugins.yaml"
        plugins_yaml.write_text(
            """
plugins:
  - id: bad_plugin
    module: test_module.NonExistent
"""
        )

        loader = PluginLoader()

        # Use a real empty module
        import types

        mock_module = types.ModuleType("test_module")
        # Don't add NonExistent attribute

        with patch("importlib.import_module", return_value=mock_module):
            with pytest.raises(ValueError, match="Plugin class.*not found"):
                loader.load_plugins_from_yaml(plugins_yaml)

    def test_load_plugin_not_subclass(self, tmp_path):
        """Test error when plugin class doesn't inherit PluginBase."""
        plugins_yaml = tmp_path / "plugins.yaml"
        plugins_yaml.write_text(
            """
plugins:
  - id: bad_plugin
    module: test_module.BadPlugin
"""
        )

        loader = PluginLoader()

        mock_module = MagicMock()

        class NotAPlugin:
            pass

        mock_module.BadPlugin = NotAPlugin

        with patch("importlib.import_module", return_value=mock_module):
            with pytest.raises(ValueError, match="does not inherit from PluginBase"):
                loader.load_plugins_from_yaml(plugins_yaml)

    def test_parse_module_path_valid(self):
        """Test parsing valid module path."""
        module_path, class_name = PluginLoader._parse_module_path(
            "my.plugins.LoggingPlugin"
        )
        assert module_path == "my.plugins"
        assert class_name == "LoggingPlugin"

    def test_parse_module_path_single_part(self):
        """Test parsing single-part module path fails."""
        with pytest.raises(ValueError, match="Invalid plugin module path"):
            PluginLoader._parse_module_path("SinglePart")

    def test_parse_module_path_no_class(self):
        """Test parsing module path without class name fails."""
        with pytest.raises(ValueError, match="Invalid plugin module path"):
            PluginLoader._parse_module_path("")


# ============================================================================
# SECTION 3: Plugin Registry Tests
# ============================================================================


class TestPluginRegistry:
    """Tests for PluginRegistry."""

    def test_register_plugin(self):
        """Test registering a plugin."""
        registry = PluginRegistry()
        plugin = MockPlugin("test_plugin")

        registry.register(plugin)

        assert "test_plugin" in registry.list_plugins()
        assert registry.get_plugin("test_plugin") == plugin
        assert plugin.startup_called

    def test_register_multiple_plugins(self):
        """Test registering multiple plugins."""
        registry = PluginRegistry()
        plugin1 = MockPlugin("plugin1")
        plugin2 = MockPlugin("plugin2")

        registry.register(plugin1)
        registry.register(plugin2)

        assert len(registry.list_plugins()) == 2
        assert registry.get_plugin("plugin1") == plugin1
        assert registry.get_plugin("plugin2") == plugin2

    def test_register_duplicate_plugin_replaces(self):
        """Test registering duplicate plugin ID replaces old one."""
        registry = PluginRegistry()
        plugin1 = MockPlugin("test")
        plugin2 = MockPlugin("test")

        registry.register(plugin1)
        registry.register(plugin2)

        assert registry.get_plugin("test") == plugin2
        assert len(registry.list_plugins()) == 1

    def test_unregister_plugin(self):
        """Test unregistering a plugin."""
        registry = PluginRegistry()
        plugin = MockPlugin("test")

        registry.register(plugin)
        registry.unregister("test")

        assert plugin.shutdown_called
        assert registry.get_plugin("test") is None
        assert len(registry.list_plugins()) == 0

    def test_unregister_nonexistent_plugin(self):
        """Test unregistering non-existent plugin does nothing."""
        registry = PluginRegistry()
        registry.unregister("nonexistent")  # Should not raise

    def test_dispatch_event_to_all_plugins(self):
        """Test event is dispatched to all registered plugins."""
        registry = PluginRegistry()
        plugin1 = MockPlugin("plugin1")
        plugin2 = MockPlugin("plugin2")

        registry.register(plugin1)
        registry.register(plugin2)

        event = Event(
            event_id="test",
            task_id="task1",
            stage_id="stage1",
            type=EventType.TASK,
            timestamp="2025-01-01T00:00:00",
            payload={"event": "test"},
        )

        registry.dispatch_event(event)

        assert len(plugin1.events_received) == 1
        assert len(plugin2.events_received) == 1
        assert plugin1.events_received[0].event_id == "test"
        assert plugin2.events_received[0].event_id == "test"

    def test_dispatch_event_immutable_copy(self):
        """Test event passed to plugin is immutable (deep copy)."""
        registry = PluginRegistry()
        plugin = MockPlugin("test")
        registry.register(plugin)

        event = Event(
            event_id="test",
            task_id="task1",
            stage_id=None,
            type=EventType.TASK,
            timestamp="2025-01-01T00:00:00",
            payload={"key": "value"},
        )

        registry.dispatch_event(event)

        # Modify original event
        event.payload["key"] = "modified"

        # Plugin should have original value
        assert plugin.events_received[0].payload["key"] == "value"

    def test_dispatch_event_plugin_error_isolated(self):
        """Test plugin error doesn't affect other plugins."""
        registry = PluginRegistry()
        error_plugin = ErrorPlugin("error")
        error_plugin.error_on_event = True

        normal_plugin = MockPlugin("normal")

        registry.register(error_plugin)
        registry.register(normal_plugin)

        event = Event(
            event_id="test",
            task_id="task1",
            stage_id=None,
            type=EventType.TASK,
            timestamp="2025-01-01T00:00:00",
            payload={"event": "test"},
        )

        # Should not raise despite error_plugin raising
        registry.dispatch_event(event)

        # Normal plugin should still receive event
        assert len(normal_plugin.events_received) == 1

    def test_register_plugin_startup_error_logged(self):
        """Test plugin startup error is logged but plugin still registered."""
        registry = PluginRegistry()
        error_plugin = ErrorPlugin("test")
        error_plugin.error_on_startup = True

        # Should not raise
        registry.register(error_plugin)

        # Plugin should still be in registry
        assert registry.get_plugin("test") is not None

    def test_unregister_plugin_shutdown_error_logged(self):
        """Test plugin shutdown error is logged but plugin still unregistered."""
        registry = PluginRegistry()
        error_plugin = ErrorPlugin("test")
        error_plugin.error_on_shutdown = True

        registry.register(error_plugin)

        # Should not raise
        registry.unregister("test")

        # Plugin should be unregistered
        assert registry.get_plugin("test") is None

    def test_clear_all_plugins(self):
        """Test clearing all plugins."""
        registry = PluginRegistry()
        plugin1 = MockPlugin("plugin1")
        plugin2 = MockPlugin("plugin2")

        registry.register(plugin1)
        registry.register(plugin2)

        registry.clear()

        assert len(registry.list_plugins()) == 0
        assert plugin1.shutdown_called
        assert plugin2.shutdown_called


# ============================================================================
# SECTION 4: Telemetry Integration Tests
# ============================================================================


class TestTelemetryPluginIntegration:
    """Tests for TelemetryBus with PluginRegistry."""

    def test_telemetry_dispatch_to_plugins(self):
        """Test TelemetryBus dispatches events to plugins."""
        registry = PluginRegistry()
        plugin = MockPlugin("test")
        registry.register(plugin)

        telemetry = TelemetryBus(plugin_registry=registry)

        event = Event(
            event_id="test",
            task_id="task1",
            stage_id=None,
            type=EventType.TASK,
            timestamp="2025-01-01T00:00:00",
            payload={"event": "test"},
        )

        telemetry.emit(event)

        assert len(plugin.events_received) == 1
        assert len(telemetry.events) == 1

    def test_telemetry_without_plugin_registry(self):
        """Test TelemetryBus works without plugin registry."""
        telemetry = TelemetryBus()

        event = Event(
            event_id="test",
            task_id="task1",
            stage_id=None,
            type=EventType.TASK,
            timestamp="2025-01-01T00:00:00",
            payload={"event": "test"},
        )

        # Should not raise
        telemetry.emit(event)

        assert len(telemetry.events) == 1


# ============================================================================
# SECTION 5: Plugin Isolation Tests
# ============================================================================


class TestPluginIsolation:
    """Tests for plugin isolation guarantees."""

    def test_plugin_cannot_mutate_event(self):
        """Test plugin cannot mutate event object."""

        class MutatingPlugin(PluginBase):
            def on_event(self, event: Event) -> None:
                event.payload["key"] = "mutated"

        registry = PluginRegistry()
        plugin = MutatingPlugin("mutating")
        registry.register(plugin)

        event = Event(
            event_id="test",
            task_id="task1",
            stage_id=None,
            type=EventType.TASK,
            timestamp="2025-01-01T00:00:00",
            payload={"key": "original"},
        )

        registry.dispatch_event(event)

        # Original event should not be mutated
        assert event.payload["key"] == "original"

    def test_plugin_exception_doesnt_affect_execution(self):
        """Test plugin exception never affects engine execution."""

        class ExceptionPlugin(PluginBase):
            def on_event(self, event: Event) -> None:
                raise RuntimeError("Plugin error")

        registry = PluginRegistry()
        plugin = ExceptionPlugin("exception")
        registry.register(plugin)

        event = Event(
            event_id="test",
            task_id="task1",
            stage_id=None,
            type=EventType.TASK,
            timestamp="2025-01-01T00:00:00",
            payload={"event": "test"},
        )

        # Should not raise despite plugin error
        registry.dispatch_event(event)

    def test_multiple_plugins_one_error(self):
        """Test one plugin error doesn't prevent other plugins."""
        registry = PluginRegistry()

        class ErrorPlugin(PluginBase):
            def __init__(self, plugin_id: str, config: dict = None):
                super().__init__(plugin_id, config)
                self.events_received = []

            def on_event(self, event: Event) -> None:
                self.events_received.append(event)
                raise RuntimeError("Error")

        error_plugin = ErrorPlugin("error")
        normal_plugin = MockPlugin("normal")

        registry.register(error_plugin)
        registry.register(normal_plugin)

        event = Event(
            event_id="test",
            task_id="task1",
            stage_id=None,
            type=EventType.TASK,
            timestamp="2025-01-01T00:00:00",
            payload={"event": "test"},
        )

        registry.dispatch_event(event)

        # Both plugins should receive event
        assert len(error_plugin.events_received) == 1
        assert len(normal_plugin.events_received) == 1
