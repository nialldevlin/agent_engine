"""Plugin registry for managing and dispatching events to plugins."""

from __future__ import annotations

import logging
from copy import deepcopy
from typing import Dict, List, Optional

from agent_engine.schemas import Event, PluginBase

logger = logging.getLogger(__name__)


class PluginRegistry:
    """Manages registered plugins and event dispatch.

    Provides:
    - Plugin registration/unregistration
    - Event dispatch to all plugins
    - Error isolation (plugin failures don't affect engine)
    - Event immutability (deep copies passed to plugins)
    """

    def __init__(self):
        """Initialize plugin registry."""
        self.plugins: Dict[str, PluginBase] = {}

    def register(self, plugin: PluginBase) -> None:
        """Register a plugin.

        Args:
            plugin: PluginBase instance to register

        Note:
            If a plugin with the same ID is already registered, it is replaced.
            The plugin's on_startup() method is called after registration.
        """
        if plugin.plugin_id in self.plugins:
            logger.warning(
                f"Plugin '{plugin.plugin_id}' already registered, replacing with new instance"
            )
            # Unregister old plugin first
            self.unregister(plugin.plugin_id)

        self.plugins[plugin.plugin_id] = plugin

        # Call plugin startup hook
        try:
            plugin.on_startup()
        except Exception as e:
            logger.error(
                f"Error in plugin '{plugin.plugin_id}'.on_startup: {e}", exc_info=True
            )

    def unregister(self, plugin_id: str) -> None:
        """Unregister a plugin.

        Args:
            plugin_id: ID of plugin to remove

        Note:
            The plugin's on_shutdown() method is called before unregistration.
            Exceptions in on_shutdown() are logged but don't prevent unregistration.
        """
        if plugin_id not in self.plugins:
            return

        plugin = self.plugins[plugin_id]

        # Call plugin shutdown hook
        try:
            plugin.on_shutdown()
        except Exception as e:
            logger.error(
                f"Error in plugin '{plugin_id}'.on_shutdown: {e}", exc_info=True
            )

        del self.plugins[plugin_id]

    def dispatch_event(self, event: Event) -> None:
        """Dispatch event to all registered plugins.

        Args:
            event: Event to dispatch (immutable copy sent to plugins)

        Note:
            - Creates an immutable deep copy of the event for each plugin
            - Plugin exceptions are caught and logged
            - Plugin failures never affect engine execution
            - Plugins are called synchronously and sequentially
        """
        # Create immutable copy of event for plugins
        event_copy = self._freeze_event(event)

        for plugin_id, plugin in self.plugins.items():
            try:
                plugin.on_event(event_copy)
            except Exception as e:
                logger.error(
                    f"Error in plugin '{plugin_id}'.on_event: {e}", exc_info=True
                )

    @staticmethod
    def _freeze_event(event: Event) -> Event:
        """Create immutable deep copy of event.

        Args:
            event: Original event

        Returns:
            Deep copy of event (prevents mutations by plugins)
        """
        return deepcopy(event)

    def get_plugin(self, plugin_id: str) -> Optional[PluginBase]:
        """Get plugin by ID.

        Args:
            plugin_id: Plugin ID to retrieve

        Returns:
            Plugin instance if found, None otherwise
        """
        return self.plugins.get(plugin_id)

    def list_plugins(self) -> List[str]:
        """List all registered plugin IDs.

        Returns:
            List of plugin IDs in insertion order
        """
        return list(self.plugins.keys())

    def clear(self) -> None:
        """Unregister all plugins.

        Note:
            Each plugin's on_shutdown() method is called.
            Exceptions are logged but don't prevent complete unregistration.
        """
        for plugin_id in list(self.plugins.keys()):
            self.unregister(plugin_id)
