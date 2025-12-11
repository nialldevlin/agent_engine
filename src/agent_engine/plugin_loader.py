"""Plugin loader for Agent Engine."""

from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import List, Optional

import yaml

from agent_engine.schemas import PluginBase, PluginConfig

logger = logging.getLogger(__name__)


class PluginLoader:
    """Loads plugins from plugins.yaml configuration file."""

    def load_plugins_from_yaml(self, yaml_path: Path) -> List[PluginBase]:
        """Load plugins from plugins.yaml file.

        Args:
            yaml_path: Path to plugins.yaml file

        Returns:
            List of initialized PluginBase instances

        Raises:
            FileNotFoundError: If plugins.yaml not found and required
            ValueError: If plugin config is invalid or module cannot be imported
        """
        if not yaml_path.exists():
            return []

        try:
            with open(yaml_path, "r") as f:
                data = yaml.safe_load(f) or {}
        except (yaml.YAMLError, IOError) as e:
            raise ValueError(f"Failed to load plugins.yaml: {e}")

        plugins_config = data.get("plugins", [])
        plugins = []

        for plugin_conf in plugins_config:
            try:
                plugin = self._load_single_plugin(plugin_conf)
                if plugin:
                    plugins.append(plugin)
            except Exception as e:
                plugin_id = plugin_conf.get("id", "unknown")
                raise ValueError(f"Failed to load plugin '{plugin_id}': {e}")

        return plugins

    def _load_single_plugin(self, plugin_conf: dict) -> Optional[PluginBase]:
        """Load a single plugin instance.

        Args:
            plugin_conf: Plugin configuration dict from YAML

        Returns:
            Initialized PluginBase instance, or None if disabled

        Raises:
            ValueError: If config is invalid or module cannot be imported
        """
        # Validate and create config
        plugin_config = PluginConfig(
            id=plugin_conf.get("id"),
            module=plugin_conf.get("module"),
            enabled=plugin_conf.get("enabled", True),
            config=plugin_conf.get("config", {}),
        )
        plugin_config.validate()

        # Skip disabled plugins
        if not plugin_config.enabled:
            return None

        # Parse module path and get class
        module_path, class_name = self._parse_module_path(plugin_config.module)

        # Dynamically import module
        try:
            module = importlib.import_module(module_path)
        except ImportError as e:
            raise ValueError(f"Cannot import plugin module '{module_path}': {e}")

        # Get plugin class from module
        try:
            plugin_class = getattr(module, class_name)
        except AttributeError as e:
            raise ValueError(
                f"Plugin class '{class_name}' not found in module '{module_path}': {e}"
            )

        # Verify class inherits from PluginBase
        if not issubclass(plugin_class, PluginBase):
            raise ValueError(
                f"Plugin class '{class_name}' does not inherit from PluginBase"
            )

        # Instantiate plugin
        try:
            plugin_instance = plugin_class(
                plugin_id=plugin_config.id, config=plugin_config.config
            )
            return plugin_instance
        except Exception as e:
            raise ValueError(f"Failed to instantiate plugin '{plugin_config.id}': {e}")

    @staticmethod
    def _parse_module_path(module_str: str) -> tuple[str, str]:
        """Parse module path to (module_path, class_name).

        Args:
            module_str: "my_app.plugins.LoggingPlugin"

        Returns:
            (module_path, class_name) tuple

        Raises:
            ValueError: If module string format is invalid
        """
        parts = module_str.rsplit(".", 1)
        if len(parts) != 2:
            raise ValueError(
                f"Invalid plugin module path: '{module_str}'. "
                f"Expected format: 'module.path.ClassName'"
            )

        return parts[0], parts[1]
