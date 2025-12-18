"""Task Scheduler for Phase 21.

Sequential task execution with FIFO queueing.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo
from uuid import uuid4

from agent_engine.schemas import SchedulerConfig, QueuedTask, TaskState


def _now_iso() -> str:
    """Generate ISO-8601 timestamp."""
    return datetime.now(ZoneInfo("UTC")).isoformat()


@dataclass
class TaskScheduler:
    """Task scheduler for Phase 21.

    Manages FIFO queue and sequential execution of tasks.
    Per v1 design: max_concurrency = 1, no true parallelism.
    """

    config: SchedulerConfig
    queue: deque = field(default_factory=deque)
    running: Dict[str, QueuedTask] = field(default_factory=dict)
    completed: Dict[str, QueuedTask] = field(default_factory=dict)
    telemetry: Optional[Any] = None

    def enqueue_task(
        self,
        input: Any,
        start_node_id: Optional[str] = None,
    ) -> str:
        """Enqueue task for later execution.

        Args:
            input: Task input data
            start_node_id: Optional explicit start node

        Returns:
            Task ID

        Raises:
            RuntimeError: If queue is full
        """
        # Check queue size limit
        if self.config.max_queue_size is not None:
            if len(self.queue) >= self.config.max_queue_size:
                error_msg = f"Queue full (limit: {self.config.max_queue_size})"
                if self.telemetry:
                    self.telemetry.emit_event("queue_full", {
                        "queue_size": len(self.queue),
                        "max_size": self.config.max_queue_size,
                    })
                raise RuntimeError(error_msg)

        # Generate task ID
        task_id = f"queued-task-{uuid4().hex[:12]}"

        # Create queued task
        queued_task = QueuedTask(
            task_id=task_id,
            input=input,
            start_node_id=start_node_id,
            state=TaskState.QUEUED,
            enqueued_at=_now_iso(),
        )

        # Add to queue
        self.queue.append(queued_task)

        return task_id

    def get_task_state(self, task_id: str) -> Optional[TaskState]:
        """Get current state of a task.

        Args:
            task_id: Task identifier

        Returns:
            TaskState, or None if task not found
        """
        # Check running
        if task_id in self.running:
            return self.running[task_id].state

        # Check completed
        if task_id in self.completed:
            return self.completed[task_id].state

        # Check queued
        for task in self.queue:
            if task.task_id == task_id:
                return task.state

        return None

    def run_next(self) -> Optional[str]:
        """Dequeue and execute one task.

        Respects max_concurrency (v1: only 1 task at a time).

        Returns:
            Task ID if executed, None if queue empty or concurrency limit hit

        Raises:
            Exception: If task execution fails
        """
        # Check concurrency limit
        if len(self.running) >= self.config.max_concurrency:
            return None

        # Check queue
        if not self.queue:
            return None

        # Dequeue task
        queued_task = self.queue.popleft()
        queued_task.state = TaskState.RUNNING
        queued_task.started_at = _now_iso()

        # Move to running
        self.running[queued_task.task_id] = queued_task

        return queued_task.task_id

    def mark_task_completed(
        self,
        task_id: str,
        output: Any = None,
    ) -> bool:
        """Mark a running task as completed.

        Args:
            task_id: Task identifier
            output: Task output

        Returns:
            True if task was found and marked, False otherwise
        """
        if task_id not in self.running:
            return False

        task = self.running.pop(task_id)
        task.state = TaskState.COMPLETED
        task.completed_at = _now_iso()
        task.output = output

        # Move to completed
        self.completed[task_id] = task

        return True

    def mark_task_failed(
        self,
        task_id: str,
        error: str,
    ) -> bool:
        """Mark a running task as failed.

        Args:
            task_id: Task identifier
            error: Error message

        Returns:
            True if task was found and marked, False otherwise
        """
        if task_id not in self.running:
            return False

        task = self.running.pop(task_id)
        task.state = TaskState.FAILED
        task.completed_at = _now_iso()
        task.error = error

        # Move to completed
        self.completed[task_id] = task

        return True

    def get_queue_size(self) -> int:
        """Get current queue length.

        Returns:
            Number of queued tasks
        """
        return len(self.queue)

    def get_running_count(self) -> int:
        """Get number of running tasks.

        Returns:
            Number of running tasks
        """
        return len(self.running)

    def get_completed_count(self) -> int:
        """Get number of completed/failed tasks.

        Returns:
            Number of completed tasks
        """
        return len(self.completed)

    def get_all_states(self) -> Dict[str, Dict[str, Any]]:
        """Get all task states (queued, running, completed).

        Returns:
            Dict mapping task_id to state info
        """
        states = {}

        # Queued tasks
        for task in self.queue:
            states[task.task_id] = {
                "state": task.state.value,
                "input": task.input,
                "start_node_id": task.start_node_id,
                "enqueued_at": task.enqueued_at,
            }

        # Running tasks
        for task_id, task in self.running.items():
            states[task_id] = {
                "state": task.state.value,
                "input": task.input,
                "start_node_id": task.start_node_id,
                "started_at": task.started_at,
            }

        # Completed tasks
        for task_id, task in self.completed.items():
            states[task_id] = {
                "state": task.state.value,
                "input": task.input,
                "start_node_id": task.start_node_id,
                "completed_at": task.completed_at,
                "output": task.output,
                "error": task.error,
            }

        return states
