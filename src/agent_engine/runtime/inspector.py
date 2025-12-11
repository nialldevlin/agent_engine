"""Inspector Mode for Phase 16.

Read-only API for querying task information without mutation capabilities.
"""

from typing import Optional, Dict, Any, List
from agent_engine.schemas import Task, UniversalStatus


class Inspector:
    """Read-only inspector for querying task state and history.

    Provides query-only access to task information, history, artifacts,
    and events without allowing task mutation or execution control.
    """

    def __init__(self, task_manager):
        """Initialize Inspector with task manager reference.

        Args:
            task_manager: TaskManager instance for data access
        """
        self.task_manager = task_manager

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID.

        Read-only access to task state. Returns immutable view
        of task data.

        Args:
            task_id: Task identifier

        Returns:
            Task instance if found, None otherwise
        """
        return self.task_manager.get_task(task_id)

    def get_task_history(self, task_id: str) -> Dict[str, Any]:
        """Get task execution history.

        Returns chronological record of task lifecycle events,
        stage executions, and status transitions.

        Args:
            task_id: Task identifier

        Returns:
            Dictionary with history data:
            {
                "task_id": str,
                "created_at": str,
                "updated_at": str,
                "status_transitions": List[Dict],
                "stage_executions": List[Dict]
            }
        """
        task = self.task_manager.get_task(task_id)
        if not task:
            return {}

        # Build status transition history
        status_transitions = []
        if hasattr(task, "created_at") and task.created_at:
            status_transitions.append({
                "status": UniversalStatus.PENDING.value if hasattr(UniversalStatus, "PENDING") else "pending",
                "timestamp": task.created_at
            })

        # Build stage execution history
        stage_executions = []
        if hasattr(task, "stage_results") and task.stage_results:
            for stage_id, record in task.stage_results.items():
                stage_executions.append({
                    "stage_id": stage_id,
                    "status": record.node_status.value if hasattr(record.node_status, "value") else str(record.node_status),
                    "started_at": record.started_at if hasattr(record, "started_at") else None,
                    "completed_at": record.completed_at if hasattr(record, "completed_at") else None,
                })

        return {
            "task_id": task_id,
            "created_at": task.created_at if hasattr(task, "created_at") else None,
            "updated_at": task.updated_at if hasattr(task, "updated_at") else None,
            "current_status": task.status.value if hasattr(task.status, "value") else str(task.status),
            "status_transitions": status_transitions,
            "stage_executions": stage_executions
        }

    def get_task_artifacts(self, task_id: str) -> Dict[str, Any]:
        """Get artifacts produced by task.

        Returns list of all artifacts (outputs, intermediate results)
        produced during task execution.

        Args:
            task_id: Task identifier

        Returns:
            Dictionary with artifact data:
            {
                "task_id": str,
                "artifacts": List[Dict]
            }
        """
        task = self.task_manager.get_task(task_id)
        if not task:
            return {"task_id": task_id, "artifacts": []}

        artifacts = []

        # Collect artifacts from stage results
        if hasattr(task, "stage_results") and task.stage_results:
            for stage_id, record in task.stage_results.items():
                if hasattr(record, "output") and record.output is not None:
                    artifacts.append({
                        "type": "stage_output",
                        "stage_id": stage_id,
                        "data": record.output
                    })

        # Add final output if available
        if hasattr(task, "current_output") and task.current_output is not None:
            artifacts.append({
                "type": "task_output",
                "data": task.current_output
            })

        return {
            "task_id": task_id,
            "artifacts": artifacts
        }

    def get_task_events(self, task_id: str) -> Dict[str, Any]:
        """Get events generated during task execution.

        Returns events (logging, errors, status changes) from
        task execution.

        Args:
            task_id: Task identifier

        Returns:
            Dictionary with event data:
            {
                "task_id": str,
                "events": List[Dict]
            }
        """
        task = self.task_manager.get_task(task_id)
        if not task:
            return {"task_id": task_id, "events": []}

        events = []

        # Collect error events from stage results
        if hasattr(task, "stage_results") and task.stage_results:
            for stage_id, record in task.stage_results.items():
                if hasattr(record, "error") and record.error is not None:
                    events.append({
                        "type": "error",
                        "stage_id": stage_id,
                        "error": record.error,
                        "timestamp": record.completed_at if hasattr(record, "completed_at") else None
                    })

        # Add task-level error if present
        if hasattr(task, "error") and task.error is not None:
            events.append({
                "type": "task_error",
                "error": task.error,
                "timestamp": task.updated_at if hasattr(task, "updated_at") else None
            })

        return {
            "task_id": task_id,
            "events": events
        }

    def get_task_summary(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get summary of task execution.

        Returns high-level summary including status, progress,
        timing, and key outputs.

        Args:
            task_id: Task identifier

        Returns:
            Dictionary with summary data or None if task not found:
            {
                "task_id": str,
                "status": str,
                "lifecycle": str,
                "created_at": str,
                "updated_at": str,
                "duration_ms": int,
                "stage_count": int,
                "completed_stages": int,
                "has_errors": bool,
                "current_output": Any
            }
        """
        task = self.task_manager.get_task(task_id)
        if not task:
            return None

        # Calculate execution duration
        duration_ms = 0
        if hasattr(task, "created_at") and hasattr(task, "updated_at") and task.created_at and task.updated_at:
            from datetime import datetime
            try:
                start = datetime.fromisoformat(task.created_at)
                end = datetime.fromisoformat(task.updated_at)
                duration_ms = int((end - start).total_seconds() * 1000)
            except Exception:
                duration_ms = 0

        # Count stages
        stage_count = len(task.stage_results) if hasattr(task, "stage_results") else 0
        completed_stages = 0
        has_errors = False

        if hasattr(task, "stage_results") and task.stage_results:
            for record in task.stage_results.values():
                if hasattr(record, "node_status"):
                    if record.node_status == UniversalStatus.COMPLETED:
                        completed_stages += 1
                    elif record.node_status == UniversalStatus.FAILED:
                        has_errors = True

        return {
            "task_id": task_id,
            "status": task.status.value if hasattr(task.status, "value") else str(task.status),
            "lifecycle": task.lifecycle.value if hasattr(task, "lifecycle") and hasattr(task.lifecycle, "value") else str(task.lifecycle) if hasattr(task, "lifecycle") else None,
            "created_at": task.created_at if hasattr(task, "created_at") else None,
            "updated_at": task.updated_at if hasattr(task, "updated_at") else None,
            "duration_ms": duration_ms,
            "stage_count": stage_count,
            "completed_stages": completed_stages,
            "has_errors": has_errors,
            "current_output": task.current_output if hasattr(task, "current_output") else None
        }
