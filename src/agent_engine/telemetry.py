"""Telemetry/event bus."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from agent_engine.schemas import Event, EventType


@dataclass
class TelemetryBus:
    events: List[Event] = field(default_factory=list)
    strict: bool = False

    def emit(self, event: Event) -> None:
        self.events.append(event)

    def task_event(self, task_id: str, payload=None) -> None:
        self.emit(Event(event_id=f"task-{len(self.events)}", task_id=task_id, stage_id=None, type=EventType.TASK, timestamp=None, payload=payload or {}))

    def error_event(self, task_id: str | None, stage_id: str | None, payload=None) -> None:
        self.emit(Event(event_id=f"error-{len(self.events)}", task_id=task_id, stage_id=stage_id, type=EventType.ERROR, timestamp=None, payload=payload or {}))
