"""Plugin manager with safe hook dispatch."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Protocol


class Plugin(Protocol):
    def __getattr__(self, name: str):
        ...


@dataclass
class PluginManager:
    strict: bool = False
    hooks: Dict[str, List[Callable]] = field(default_factory=lambda: {})

    def register(self, plugin: Plugin) -> None:
        for attr in dir(plugin):
            if attr.startswith("on_"):
                self.hooks.setdefault(attr, []).append(getattr(plugin, attr))

    def emit(self, hook: str, **kwargs) -> None:
        for handler in self.hooks.get(hook, []):
            try:
                handler(**kwargs)
            except Exception:
                if self.strict:
                    raise
                # swallow in non-strict mode


class LoggingPlugin:
    """Sample plugin that records events into an in-memory list."""

    def __init__(self, sink: List[str]):
        self.sink = sink

    def on_before_task(self, task_id: str) -> None:
        self.sink.append(f"before_task:{task_id}")

    def on_after_task(self, task_id: str) -> None:
        self.sink.append(f"after_task:{task_id}")
