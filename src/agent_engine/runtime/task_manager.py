"""Task Manager handles Task lifecycle and persistence."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional

from agent_engine.schemas import (
    RoutingDecision,
    StageExecutionRecord,
    Task,
    TaskMode,
    TaskSpec,
    TaskStatus,
)

def _generate_task_id(spec: TaskSpec) -> str:
    from uuid import uuid4

    return f"task-{spec.task_spec_id}-{uuid4().hex[:8]}"


def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


@dataclass
class TaskManager:
    tasks: Dict[str, Task] = field(default_factory=dict)

    def create_task(self, spec: TaskSpec, pipeline_id: str, task_id: str | None = None) -> Task:
        task = Task(
            task_id=task_id or _generate_task_id(spec),
            spec=spec,
            status=TaskStatus.PENDING,
            pipeline_id=pipeline_id,
            created_at=_now_iso(),
            updated_at=_now_iso(),
        )
        self.tasks[task.task_id] = task
        return task

    def set_status(self, task: Task, status: TaskStatus) -> None:
        task.status = status
        task.updated_at = _now_iso()

    def set_current_stage(self, task: Task, stage_id: Optional[str]) -> None:
        task.current_stage_id = stage_id
        task.updated_at = _now_iso()

    def record_stage_result(self, task: Task, stage_id: str, output=None, error=None, started_at: Optional[str] = None) -> None:
        task.stage_results[stage_id] = StageExecutionRecord(
            output=output,
            error=error,
            started_at=started_at or task.stage_results.get(stage_id, StageExecutionRecord()).started_at or _now_iso(),
            completed_at=_now_iso(),
        )
        task.updated_at = _now_iso()

    def append_routing(self, task: Task, stage_id: str, decision: Optional[str], agent_id: Optional[str]) -> None:
        task.routing_trace.append(
            RoutingDecision(stage_id=stage_id, decision=decision, agent_id=agent_id, timestamp=_now_iso())
        )
        task.updated_at = _now_iso()
