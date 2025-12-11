"""Telemetry/event bus."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, List, Optional
from zoneinfo import ZoneInfo
import time

from agent_engine.schemas import Event, EventType, MetricSample

if TYPE_CHECKING:
    from agent_engine.plugin_registry import PluginRegistry
    from agent_engine.runtime.metrics_collector import MetricsCollector


def _now_iso() -> str:
    """Generate ISO-8601 timestamp."""
    return datetime.now(ZoneInfo("UTC")).isoformat()


@dataclass
class TelemetryBus:
    events: List[Event] = field(default_factory=list)
    strict: bool = False
    plugin_registry: Optional[PluginRegistry] = field(default=None)
    metrics_collector: Optional[MetricsCollector] = field(default=None)

    def __post_init__(self):
        """Initialize start time tracking dicts."""
        self._node_start_times: dict[str, float] = {}
        self._tool_start_times: dict[str, float] = {}

    def emit(self, event: Event) -> None:
        """Emit event to bus and dispatch to plugins.

        Args:
            event: Event to emit
        """
        self.events.append(event)

        # Dispatch to plugins if registry available
        if self.plugin_registry:
            self.plugin_registry.dispatch_event(event)

    def task_event(self, task_id: str, payload=None) -> None:
        self.emit(Event(event_id=f"task-{len(self.events)}", task_id=task_id, stage_id=None, type=EventType.TASK, timestamp=None, payload=payload or {}))

    def error_event(self, task_id: str | None, stage_id: str | None, payload=None) -> None:
        self.emit(Event(event_id=f"error-{len(self.events)}", task_id=task_id, stage_id=stage_id, type=EventType.ERROR, timestamp=None, payload=payload or {}))

    # Task Events
    def task_started(self, task_id: str, spec: Any, mode: str) -> None:
        """Emit task started event."""
        self.emit(Event(
            event_id=f"task_started-{len(self.events)}",
            task_id=task_id,
            stage_id=None,
            type=EventType.TASK,
            timestamp=_now_iso(),
            payload={
                "event": "task_started",
                "spec": spec.model_dump() if hasattr(spec, 'model_dump') else str(spec),
                "mode": mode
            }
        ))

    def task_completed(self, task_id: str, status: str, lifecycle: str, output: Any) -> None:
        """Emit task completed event."""
        self.emit(Event(
            event_id=f"task_completed-{len(self.events)}",
            task_id=task_id,
            stage_id=None,
            type=EventType.TASK,
            timestamp=_now_iso(),
            payload={
                "event": "task_completed",
                "status": status,
                "lifecycle": lifecycle,
                "output": output
            }
        ))

    def task_failed(self, task_id: str, error: Any) -> None:
        """Emit task failed event."""
        self.emit(Event(
            event_id=f"task_failed-{len(self.events)}",
            task_id=task_id,
            stage_id=None,
            type=EventType.TASK,
            timestamp=_now_iso(),
            payload={
                "event": "task_failed",
                "error": str(error)
            }
        ))

    # Node Events
    def node_started(self, task_id: str, node_id: str, role: str, kind: str, input_data: Any) -> None:
        """Emit node started event."""
        # Store start time for duration calculation
        key = f"{task_id}:{node_id}"
        self._node_start_times[key] = time.time()

        # Emit event
        self.emit(Event(
            event_id=f"node_started-{len(self.events)}",
            task_id=task_id,
            stage_id=node_id,
            type=EventType.STAGE,
            timestamp=_now_iso(),
            payload={
                "event": "node_started",
                "role": role,
                "kind": kind,
                "input": input_data
            }
        ))

        # Record counter metric
        if self.metrics_collector:
            self.metrics_collector.record_counter(
                "node_execution_count",
                tags={"task_id": task_id, "node_id": node_id, "role": role, "kind": kind}
            )

    def node_completed(self, task_id: str, node_id: str, output: Any, status: str) -> None:
        """Emit node completed event."""
        # Calculate duration and record timer metric
        key = f"{task_id}:{node_id}"
        if key in self._node_start_times:
            duration_ms = (time.time() - self._node_start_times[key]) * 1000
            del self._node_start_times[key]

            # Record timer metric
            if self.metrics_collector:
                self.metrics_collector.record_timer(
                    "node_execution_duration",
                    duration_ms,
                    tags={"task_id": task_id, "node_id": node_id, "status": status}
                )

        # Emit event
        self.emit(Event(
            event_id=f"node_completed-{len(self.events)}",
            task_id=task_id,
            stage_id=node_id,
            type=EventType.STAGE,
            timestamp=_now_iso(),
            payload={
                "event": "node_completed",
                "output": output,
                "status": status
            }
        ))

    def node_failed(self, task_id: str, node_id: str, error: Any) -> None:
        """Emit node failed event."""
        self.emit(Event(
            event_id=f"node_failed-{len(self.events)}",
            task_id=task_id,
            stage_id=node_id,
            type=EventType.STAGE,
            timestamp=_now_iso(),
            payload={
                "event": "node_failed",
                "error": str(error)
            }
        ))

    # Routing Events
    def routing_decision(self, task_id: str, node_id: str, decision: str, next_node_id: str) -> None:
        """Emit routing decision event."""
        self.emit(Event(
            event_id=f"routing_decision-{len(self.events)}",
            task_id=task_id,
            stage_id=node_id,
            type=EventType.ROUTING,
            timestamp=_now_iso(),
            payload={
                "event": "routing_decision",
                "decision": decision,
                "next_node_id": next_node_id
            }
        ))

    def routing_branch(self, task_id: str, node_id: str, clone_count: int, clone_ids: List[str]) -> None:
        """Emit routing branch event."""
        self.emit(Event(
            event_id=f"routing_branch-{len(self.events)}",
            task_id=task_id,
            stage_id=node_id,
            type=EventType.ROUTING,
            timestamp=_now_iso(),
            payload={
                "event": "routing_branch",
                "clone_count": clone_count,
                "clone_ids": clone_ids
            }
        ))

    def routing_split(self, task_id: str, node_id: str, subtask_count: int, subtask_ids: List[str]) -> None:
        """Emit routing split event."""
        self.emit(Event(
            event_id=f"routing_split-{len(self.events)}",
            task_id=task_id,
            stage_id=node_id,
            type=EventType.ROUTING,
            timestamp=_now_iso(),
            payload={
                "event": "routing_split",
                "subtask_count": subtask_count,
                "subtask_ids": subtask_ids
            }
        ))

    def routing_merge(self, task_id: str, node_id: str, input_count: int, input_statuses: List[str]) -> None:
        """Emit routing merge event."""
        self.emit(Event(
            event_id=f"routing_merge-{len(self.events)}",
            task_id=task_id,
            stage_id=node_id,
            type=EventType.ROUTING,
            timestamp=_now_iso(),
            payload={
                "event": "routing_merge",
                "input_count": input_count,
                "input_statuses": input_statuses
            }
        ))

    # Tool Events
    def tool_invoked(self, task_id: str, node_id: str, tool_id: str, inputs: Any) -> None:
        """Emit tool invoked event."""
        # Store tool start time
        key = f"{task_id}:{node_id}:{tool_id}"
        self._tool_start_times[key] = time.time()

        # Emit event
        self.emit(Event(
            event_id=f"tool_invoked-{len(self.events)}",
            task_id=task_id,
            stage_id=node_id,
            type=EventType.TOOL,
            timestamp=_now_iso(),
            payload={
                "event": "tool_invoked",
                "tool_id": tool_id,
                "inputs": inputs
            }
        ))

        # Record counter metric
        if self.metrics_collector:
            self.metrics_collector.record_counter(
                "tool_invocation_count",
                tags={"task_id": task_id, "tool_name": tool_id}
            )

    def tool_completed(self, task_id: str, node_id: str, tool_id: str, output: Any, status: str) -> None:
        """Emit tool completed event."""
        # Calculate duration and record timer metric
        key = f"{task_id}:{node_id}:{tool_id}"
        if key in self._tool_start_times:
            duration_ms = (time.time() - self._tool_start_times[key]) * 1000
            del self._tool_start_times[key]

            # Record timer metric
            if self.metrics_collector:
                self.metrics_collector.record_timer(
                    "tool_invocation_duration",
                    duration_ms,
                    tags={"task_id": task_id, "tool_name": tool_id}
                )

        # Emit event
        self.emit(Event(
            event_id=f"tool_completed-{len(self.events)}",
            task_id=task_id,
            stage_id=node_id,
            type=EventType.TOOL,
            timestamp=_now_iso(),
            payload={
                "event": "tool_completed",
                "tool_id": tool_id,
                "output": output,
                "status": status
            }
        ))

    def tool_failed(self, task_id: str, node_id: str, tool_id: str, error: Any) -> None:
        """Emit tool failed event."""
        self.emit(Event(
            event_id=f"tool_failed-{len(self.events)}",
            task_id=task_id,
            stage_id=node_id,
            type=EventType.TOOL,
            timestamp=_now_iso(),
            payload={
                "event": "tool_failed",
                "tool_id": tool_id,
                "error": str(error)
            }
        ))

    # Context Events
    def context_assembled(self, task_id: str, node_id: str, profile_id: str, item_count: int, token_count: int) -> None:
        """Emit context assembled event."""
        self.emit(Event(
            event_id=f"context_assembled-{len(self.events)}",
            task_id=task_id,
            stage_id=node_id,
            type=EventType.MEMORY,
            timestamp=_now_iso(),
            payload={
                "event": "context_assembled",
                "profile_id": profile_id,
                "item_count": item_count,
                "token_count": token_count
            }
        ))

    def context_failed(self, task_id: str, node_id: str, error: Any) -> None:
        """Emit context failed event."""
        self.emit(Event(
            event_id=f"context_failed-{len(self.events)}",
            task_id=task_id,
            stage_id=node_id,
            type=EventType.MEMORY,
            timestamp=_now_iso(),
            payload={
                "event": "context_failed",
                "error": str(error)
            }
        ))

    # Clone/Subtask Events
    def clone_created(self, parent_task_id: str, clone_id: str, node_id: str, lineage: Any) -> None:
        """Emit clone created event."""
        self.emit(Event(
            event_id=f"clone_created-{len(self.events)}",
            task_id=parent_task_id,
            stage_id=node_id,
            type=EventType.TASK,
            timestamp=_now_iso(),
            payload={
                "event": "clone_created",
                "clone_id": clone_id,
                "lineage": lineage.model_dump() if hasattr(lineage, 'model_dump') else str(lineage)
            }
        ))

    def subtask_created(self, parent_task_id: str, subtask_id: str, node_id: str, lineage: Any) -> None:
        """Emit subtask created event."""
        self.emit(Event(
            event_id=f"subtask_created-{len(self.events)}",
            task_id=parent_task_id,
            stage_id=node_id,
            type=EventType.TASK,
            timestamp=_now_iso(),
            payload={
                "event": "subtask_created",
                "subtask_id": subtask_id,
                "lineage": lineage.model_dump() if hasattr(lineage, 'model_dump') else str(lineage)
            }
        ))

    # Policy Events (Phase 14)
    def emit_policy_denied(self, target: str, reason: str, task_id: str = "") -> None:
        """Emit policy denied event.

        Args:
            target: Target that was denied (tool name, etc.)
            reason: Reason for denial
            task_id: Optional task ID
        """
        self.emit(Event(
            event_id=f"policy_denied-{len(self.events)}",
            task_id=task_id or None,
            stage_id=None,
            type=EventType.ERROR,
            timestamp=_now_iso(),
            payload={
                "event": "policy_denied",
                "target": target,
                "reason": reason,
            }
        ))

        # Record counter metric
        if self.metrics_collector:
            self.metrics_collector.record_counter(
                "policy_denial_count",
                tags={"target": target}
            )

    def get_metrics(self) -> List[MetricSample]:
        """Get all collected metrics."""
        if self.metrics_collector:
            return self.metrics_collector.get_samples()
        return []
