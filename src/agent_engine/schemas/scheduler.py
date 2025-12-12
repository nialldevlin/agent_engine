"""Scheduler schemas for Phase 21.

Defines configurations and states for task scheduling and execution.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Optional


class TaskState(str, Enum):
    """Task lifecycle states in scheduler."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class QueuePolicy(str, Enum):
    """Queue scheduling policies."""
    FIFO = "fifo"


@dataclass
class SchedulerConfig:
    """Scheduler configuration.

    Per canonical design:
    - enabled: Whether scheduler is active
    - max_concurrency: Max concurrent tasks (default 1 for v1)
    - queue_policy: Queue policy (only FIFO in v1)
    - max_queue_size: Max queue capacity (None = unbounded)
    """
    enabled: bool = True
    max_concurrency: int = 1
    queue_policy: QueuePolicy = QueuePolicy.FIFO
    max_queue_size: Optional[int] = None

    def validate(self) -> None:
        """Validate configuration."""
        if self.max_concurrency < 1:
            raise ValueError("max_concurrency must be >= 1")

        if self.max_queue_size is not None and self.max_queue_size < 1:
            raise ValueError("max_queue_size must be >= 1 or None (unbounded)")

        if self.queue_policy not in [QueuePolicy.FIFO]:
            raise ValueError(f"Unsupported queue_policy: {self.queue_policy}")


@dataclass
class QueuedTask:
    """Task in scheduler queue."""
    task_id: str
    input: Any
    start_node_id: Optional[str] = None
    state: TaskState = TaskState.QUEUED
    enqueued_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    output: Any = None
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)
