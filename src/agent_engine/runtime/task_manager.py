"""Task Manager handles Task lifecycle and persistence."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from agent_engine.schemas import (
    EngineError,
    EngineErrorCode,
    EngineErrorSource,
    RoutingDecision,
    Severity,
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
    from zoneinfo import ZoneInfo

    return datetime.now(ZoneInfo("UTC")).isoformat()


def _extract_project_id(task_id: str) -> str:
    """Extract project_id from task_id.
    
    Convention: task-{spec_id}-{uuid_suffix}
    Project ID is the spec_id (middle segment).
    
    Args:
        task_id: Task identifier string
        
    Returns:
        Project identifier, or "default" if parsing fails
        
    Example:
        "task-myproject-abc123" -> "myproject"
        "task-user_req_5-def456" -> "user_req_5"
        "invalid-format" -> "default"
    """
    parts = task_id.split("-")
    if len(parts) >= 3:
        # Join all middle parts (supports multi-part spec_ids)
        return "-".join(parts[1:-1])
    return "default"


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

    def save_checkpoint(
        self,
        task_id: str,
        storage_root: Path = Path(".agent_engine/tasks")
    ) -> Optional[EngineError]:
        """Save task to disk as JSON checkpoint.
        
        Creates directory structure: {storage_root}/{project_id}/{task_id}.json
        Overwrites existing checkpoint if present.
        
        Args:
            task_id: Task identifier
            storage_root: Base directory for task storage
            
        Returns:
            None on success, EngineError on failure
            
        Error Cases:
            - Task not in memory: code=VALIDATION
            - IO failure: code=UNKNOWN
        """
        # 1. Check task exists in memory
        task = self.tasks.get(task_id)
        if task is None:
            return EngineError(
                error_id="task_not_found",
                code=EngineErrorCode.VALIDATION,
                message=f"Task '{task_id}' not found in memory",
                source=EngineErrorSource.TASK_MANAGER,
                severity=Severity.ERROR
            )
        
        # 2. Extract project ID and build path
        project_id = _extract_project_id(task_id)
        task_file = storage_root / project_id / f"{task_id}.json"
        
        # 3. Serialize task
        try:
            task_data = task.to_dict()
        except Exception as e:
            return EngineError(
                error_id="serialization_failed",
                code=EngineErrorCode.UNKNOWN,
                message=f"Failed to serialize task: {e}",
                source=EngineErrorSource.TASK_MANAGER,
                severity=Severity.ERROR
            )
        
        # 4. Write to disk (create dirs as needed)
        try:
            task_file.parent.mkdir(parents=True, exist_ok=True)
            task_file.write_text(json.dumps(task_data, indent=2))
            return None
        except IOError as e:
            return EngineError(
                error_id="checkpoint_save_failed",
                code=EngineErrorCode.UNKNOWN,
                message=f"IO error saving checkpoint: {e}",
                source=EngineErrorSource.TASK_MANAGER,
                severity=Severity.ERROR,
                details={"path": str(task_file)}
            )

    def load_checkpoint(
        self,
        task_id: str,
        storage_root: Path = Path(".agent_engine/tasks")
    ) -> Tuple[Optional[Task], Optional[EngineError]]:
        """Load task from disk checkpoint.
        
        Restores task into memory (self.tasks dict).
        Overwrites any existing in-memory task with same ID.
        
        Args:
            task_id: Task identifier
            storage_root: Base directory for task storage
            
        Returns:
            (Task, None) on success
            (None, EngineError) on failure
            
        Error Cases:
            - File not found: code=VALIDATION
            - Invalid JSON: code=JSON
            - Schema violation: code=VALIDATION
        """
        # 1. Build path
        project_id = _extract_project_id(task_id)
        task_file = storage_root / project_id / f"{task_id}.json"
        
        # 2. Check file exists
        if not task_file.exists():
            return None, EngineError(
                error_id="checkpoint_not_found",
                code=EngineErrorCode.VALIDATION,
                message=f"Checkpoint file not found: {task_file}",
                source=EngineErrorSource.TASK_MANAGER,
                severity=Severity.ERROR
            )
        
        # 3. Read and parse JSON
        try:
            task_data = json.loads(task_file.read_text())
        except json.JSONDecodeError as e:
            return None, EngineError(
                error_id="invalid_checkpoint_json",
                code=EngineErrorCode.JSON,
                message=f"Failed to parse checkpoint JSON: {e}",
                source=EngineErrorSource.TASK_MANAGER,
                severity=Severity.ERROR,
                details={"path": str(task_file)}
            )
        
        # 4. Deserialize Task
        try:
            task = Task.from_dict(task_data)
        except Exception as e:
            return None, EngineError(
                error_id="invalid_checkpoint_schema",
                code=EngineErrorCode.VALIDATION,
                message=f"Checkpoint data violates Task schema: {e}",
                source=EngineErrorSource.TASK_MANAGER,
                severity=Severity.ERROR,
                details={"path": str(task_file)}
            )
        
        # 5. Store in memory
        self.tasks[task_id] = task
        return task, None

    def list_tasks(
        self,
        project_id: str,
        storage_root: Path = Path(".agent_engine/tasks")
    ) -> Tuple[List[str], Optional[EngineError]]:
        """List all task IDs for a project.
        
        Scans {storage_root}/{project_id}/ for .json files.
        Returns empty list if directory doesn't exist (not an error).
        
        Args:
            project_id: Project identifier
            storage_root: Base directory for task storage
            
        Returns:
            (list_of_task_ids, None) on success
            ([], EngineError) on permission error
            
        Note:
            Missing directory returns ([], None) - NOT an error.
        """
        project_dir = storage_root / project_id
        
        # Directory doesn't exist = no tasks (not an error)
        if not project_dir.exists():
            return [], None
        
        try:
            # Find all .json files, extract task_id from filename
            json_files = list(project_dir.glob("*.json"))
            task_ids = sorted([f.stem for f in json_files])
            return task_ids, None
        except PermissionError as e:
            return [], EngineError(
                error_id="permission_denied",
                code=EngineErrorCode.UNKNOWN,
                message=f"Permission denied accessing {project_dir}: {e}",
                source=EngineErrorSource.TASK_MANAGER,
                severity=Severity.ERROR
            )

    def get_task_metadata(
        self,
        task_id: str,
        storage_root: Path = Path(".agent_engine/tasks")
    ) -> Tuple[Optional[Dict[str, Any]], Optional[EngineError]]:
        """Get task metadata without loading full task into memory.
        
        Reads only required fields: task_id, status, pipeline_id, timestamps.
        Lightweight operation for querying task history.
        
        Args:
            task_id: Task identifier
            storage_root: Base directory for task storage
            
        Returns:
            (metadata_dict, None) on success
            (None, EngineError) on failure
            
        Metadata dict structure:
            {
                "task_id": str,
                "status": str,
                "pipeline_id": str,
                "created_at": Optional[str],
                "updated_at": Optional[str]
            }
        """
        # 1. Build path
        project_id = _extract_project_id(task_id)
        task_file = storage_root / project_id / f"{task_id}.json"
        
        # 2. Check file exists
        if not task_file.exists():
            return None, EngineError(
                error_id="checkpoint_not_found",
                code=EngineErrorCode.VALIDATION,
                message=f"Checkpoint file not found: {task_file}",
                source=EngineErrorSource.TASK_MANAGER,
                severity=Severity.ERROR
            )
        
        # 3. Read and parse JSON
        try:
            task_data = json.loads(task_file.read_text())
        except json.JSONDecodeError as e:
            return None, EngineError(
                error_id="invalid_checkpoint_json",
                code=EngineErrorCode.JSON,
                message=f"Failed to parse checkpoint JSON: {e}",
                source=EngineErrorSource.TASK_MANAGER,
                severity=Severity.ERROR
            )
        
        # 4. Extract metadata fields only
        metadata = {
            "task_id": task_data.get("task_id"),
            "status": task_data.get("status"),
            "pipeline_id": task_data.get("pipeline_id"),
            "created_at": task_data.get("created_at"),
            "updated_at": task_data.get("updated_at")
        }
        
        return metadata, None
