"""Plugin schemas and interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .event import Event


@dataclass
class PluginConfig:
    """Plugin configuration from plugins.yaml."""

    id: str
    module: str
    enabled: bool = True
    config: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        """Validate plugin configuration.

        Raises:
            ValueError: If configuration is invalid
        """
        if not self.id or not isinstance(self.id, str):
            raise ValueError("Plugin id required and must be string")
        if not self.module or not isinstance(self.module, str):
            raise ValueError("Plugin module required and must be string")
        if not isinstance(self.enabled, bool):
            raise ValueError("Plugin enabled must be boolean")
        if not isinstance(self.config, dict):
            raise ValueError("Plugin config must be dict")


class PluginBase(ABC):
    """Base class for all plugins (read-only observers with optional extensions).

    Plugins observe engine events and perform logging, metrics, or other
    read-only operations. Plugins MAY optionally register extensions
    (e.g., LLM providers) via register_extensions; core execution flow
    remains controlled by the engine.

    Plugin exceptions are caught and logged; they never affect engine execution.
    """

    def __init__(self, plugin_id: str, config: Optional[Dict[str, Any]] = None):
        """Initialize plugin.

        Args:
            plugin_id: Unique plugin identifier
            config: Plugin-specific configuration dict
        """
        self.plugin_id = plugin_id
        self.config = config or {}

    @abstractmethod
    def on_event(self, event: Event) -> None:
        """Handle engine event (read-only).

        This method is called synchronously for each event emitted by the engine.
        The event is passed as an immutable copy; mutations have no effect.

        Args:
            event: Immutable engine event

        Note:
            - Plugin must not mutate event object
            - Plugin must not access engine internals
            - Any exceptions raised are caught and logged
            - Plugin failures never affect engine execution
        """
        pass

    def on_startup(self) -> None:
        """Called when plugin is registered.

        Override this method to perform initialization (e.g., open files,
        connect to external services).

        Default implementation does nothing.
        """
        pass

    def on_shutdown(self) -> None:
        """Called when plugin is unregistered.

        Override this method to perform cleanup (e.g., close files,
        flush metrics).

        Default implementation does nothing.
        """
        pass

    def register_extensions(self, adapters) -> None:
        """Optional hook to register runtime extensions (e.g., LLM providers).

        Args:
            adapters: AdapterRegistry instance

        Default implementation does nothing.
        """
        # Plugins can override to register LLM provider factories or tool adapters.
        return None
