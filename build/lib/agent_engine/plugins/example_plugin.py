"""Example plugin demonstrating read-only event observation."""

import logging
from agent_engine.schemas import Event, PluginBase

logger = logging.getLogger(__name__)


class ExampleLoggingPlugin(PluginBase):
    """Example plugin that logs all engine events.

    This plugin demonstrates the read-only observer pattern:
    - Receives all events from the engine
    - Cannot mutate events or access engine internals
    - Exceptions are caught and logged, never affecting engine execution
    """

    def __init__(self, plugin_id: str, config: dict = None):
        """Initialize example logging plugin.

        Args:
            plugin_id: Unique plugin identifier
            config: Optional plugin configuration dict
                   - log_level: "DEBUG", "INFO", "WARNING" (default: "INFO")
                   - log_all: bool, whether to log all events (default: True)
        """
        super().__init__(plugin_id, config)
        self.event_count = 0
        self.log_level = self.config.get("log_level", "INFO").upper()

    def on_startup(self) -> None:
        """Called when plugin is registered."""
        logger.info(f"ExampleLoggingPlugin '{self.plugin_id}' started")

    def on_event(self, event: Event) -> None:
        """Handle engine event (read-only).

        Args:
            event: Immutable engine event

        Note:
            This plugin NEVER modifies the event or engine state.
        """
        self.event_count += 1

        # Log event details
        log_msg = (
            f"[Event {self.event_count}] "
            f"type={event.type.value} "
            f"task_id={event.task_id} "
            f"stage_id={event.stage_id} "
            f"event={event.payload.get('event', 'unknown')}"
        )

        if self.log_level == "DEBUG":
            logger.debug(log_msg + f" payload={event.payload}")
        else:
            logger.info(log_msg)

    def on_shutdown(self) -> None:
        """Called when plugin is unregistered."""
        logger.info(
            f"ExampleLoggingPlugin '{self.plugin_id}' shutdown. "
            f"Processed {self.event_count} events"
        )
