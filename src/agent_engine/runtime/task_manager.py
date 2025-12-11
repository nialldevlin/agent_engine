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
    TaskLifecycle,
    TaskMode,
    TaskSpec,
    UniversalStatus,
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

    def create_task(self, spec: TaskSpec, task_id: str | None = None) -> Task:
        generated_task_id = task_id or _generate_task_id(spec)
        project_id = _extract_project_id(generated_task_id)
        task = Task(
            task_id=generated_task_id,
            spec=spec,
            lifecycle=TaskLifecycle.QUEUED,
            status=UniversalStatus.PENDING,
            created_at=_now_iso(),
            updated_at=_now_iso(),
            task_memory_ref=f"task_memory:{generated_task_id}",
            project_memory_ref=f"project_memory:{project_id}",
            global_memory_ref="global_memory:default",
        )
        self.tasks[task.task_id] = task
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID.

        Args:
            task_id: Task identifier

        Returns:
            Task if found, None otherwise
        """
        return self.tasks.get(task_id)

    def set_status(self, task: Task, status: UniversalStatus) -> None:
        task.status = status
        task.updated_at = _now_iso()

    def set_current_stage(self, task: Task, stage_id: Optional[str]) -> None:
        task.current_stage_id = stage_id
        task.updated_at = _now_iso()

    def record_stage_result(self, task: Task, stage_id: str, record: StageExecutionRecord = None, output=None, error=None, started_at: Optional[str] = None) -> None:
        """Record complete stage execution record.

        Supports both new (record parameter) and legacy (output/error/started_at) signatures.

        Args:
            task: Task to update
            stage_id: Stage identifier
            record: Complete StageExecutionRecord from NodeExecutor (new style)
            output: Output payload (legacy style)
            error: Error object (legacy style)
            started_at: Start timestamp (legacy style)
        """
        if record is not None:
            # New style: full StageExecutionRecord provided
            task.stage_results[stage_id] = record
        else:
            # Legacy style: import here to avoid circular imports
            from agent_engine.schemas import NodeRole, NodeKind, UniversalStatus

            # Get start time: use provided value, existing record's value, or current time
            final_started_at = started_at
            if not final_started_at:
                existing = task.stage_results.get(stage_id)
                final_started_at = existing.started_at if existing and hasattr(existing, 'started_at') else _now_iso()

            # Build minimal StageExecutionRecord from legacy components
            task.stage_results[stage_id] = StageExecutionRecord(
                node_id=stage_id,
                node_role=NodeRole.LINEAR,  # Default fallback
                node_kind=NodeKind.DETERMINISTIC,  # Default fallback
                output=output,
                error=error,
                node_status=UniversalStatus.COMPLETED if error is None else UniversalStatus.FAILED,
                started_at=final_started_at,
                completed_at=_now_iso(),
            )
        task.updated_at = _now_iso()

    def append_routing(self, task: Task, stage_id: str, decision: Optional[str], agent_id: Optional[str]) -> None:
        task.routing_trace.append(
            RoutingDecision(stage_id=stage_id, decision=decision, agent_id=agent_id, timestamp=_now_iso())
        )
        task.updated_at = _now_iso()

    def create_clone(
        self,
        parent: Task,
        branch_label: str,
        output: Optional[Any] = None
    ) -> Task:
        """Create a clone task from a Branch node execution.

        Clones inherit the parent's spec and memory refs but get a new task_id.
        The parent's output becomes the clone's initial state.

        Args:
            parent: Parent task being cloned
            branch_label: Edge label identifying which branch was taken
            output: Output from the branch node (optional)

        Returns:
            New clone task with proper lineage tracking
        """
        clone_id = f"{parent.task_id}-clone-{len(parent.child_task_ids)}"
        clone = Task(
            task_id=clone_id,
            spec=parent.spec,  # Inherit parent spec
            lifecycle=TaskLifecycle.QUEUED,
            status=UniversalStatus.PENDING,
            current_output=output or parent.current_output,
            parent_task_id=parent.task_id,
            lineage_type="clone",
            lineage_metadata={
                "branch_label": branch_label,
                "cloned_at_stage": parent.current_stage_id,
                "clone_index": len(parent.child_task_ids)
            },
            task_memory_ref=f"task_memory:{clone_id}",
            project_memory_ref=parent.project_memory_ref,  # Inherit project memory
            global_memory_ref=parent.global_memory_ref,  # Inherit global memory
            created_at=_now_iso(),
            updated_at=_now_iso(),
        )

        # Track child relationship
        parent.child_task_ids.append(clone_id)
        parent.updated_at = _now_iso()

        # Store clone in manager
        self.tasks[clone_id] = clone

        return clone

    def create_subtask(
        self,
        parent: Task,
        subtask_input: Any,
        split_edge_label: Optional[str] = None
    ) -> Task:
        """Create a subtask from a Split node execution.

        Subtasks get a new input payload derived from the parent's split logic.
        Each subtask is an independent unit of work with its own lifecycle.

        Args:
            parent: Parent task being split
            subtask_input: Input payload for this subtask
            split_edge_label: Edge label identifying which split branch (optional)

        Returns:
            New subtask with proper lineage tracking
        """
        subtask_index = len(parent.child_task_ids)
        subtask_id = f"{parent.task_id}-subtask-{subtask_index}"

        # Create new spec for subtask with its own input
        subtask_spec = TaskSpec(
            task_spec_id=f"{parent.spec.task_spec_id}-subtask-{subtask_index}",
            request=str(subtask_input),  # Convert input to request string
            mode=parent.spec.mode,
            priority=parent.spec.priority,
            hints=parent.spec.hints,
            files=parent.spec.files,
            overrides=parent.spec.overrides,
            metadata=parent.spec.metadata.copy()
        )

        subtask = Task(
            task_id=subtask_id,
            spec=subtask_spec,
            lifecycle=TaskLifecycle.QUEUED,
            status=UniversalStatus.PENDING,
            current_output=None,  # Subtask starts fresh
            parent_task_id=parent.task_id,
            lineage_type="subtask",
            lineage_metadata={
                "split_edge_label": split_edge_label,
                "split_at_stage": parent.current_stage_id,
                "subtask_index": subtask_index,
                "subtask_input": subtask_input
            },
            task_memory_ref=f"task_memory:{subtask_id}",
            project_memory_ref=parent.project_memory_ref,  # Inherit project memory
            global_memory_ref=parent.global_memory_ref,  # Inherit global memory
            created_at=_now_iso(),
            updated_at=_now_iso(),
        )

        # Track child relationship
        parent.child_task_ids.append(subtask_id)
        parent.updated_at = _now_iso()

        # Store subtask in manager
        self.tasks[subtask_id] = subtask

        return subtask

    def get_children(self, parent_id: str) -> List[Task]:
        """Get all child tasks (clones and subtasks) of a parent.

        Args:
            parent_id: Parent task ID

        Returns:
            List of child Task objects (may be empty)
        """
        parent = self.tasks.get(parent_id)
        if not parent:
            return []

        return [
            self.tasks[child_id]
            for child_id in parent.child_task_ids
            if child_id in self.tasks
        ]

    def check_clone_completion(self, parent_id: str) -> bool:
        """Check if parent task can complete based on clone completion rules.

        Per AGENT_ENGINE_SPEC §2.1: Parent completes when ANY one clone succeeds.
        Per Phase 7: If some clones fail but parent allows partial, parent enters PARTIAL.

        Args:
            parent_id: Parent task ID

        Returns:
            True if at least one clone has reached terminal state (COMPLETED, FAILED, or PARTIAL)
        """
        parent = self.tasks.get(parent_id)
        if not parent or not parent.child_task_ids:
            return False

        completed_clones = []
        failed_clones = []

        for child_id in parent.child_task_ids:
            child = self.tasks.get(child_id)
            if child and child.lineage_type == "clone":
                if child.status == UniversalStatus.COMPLETED:
                    completed_clones.append(child)
                elif child.status == UniversalStatus.FAILED:
                    failed_clones.append(child)

        # Parent succeeds if any clone succeeds
        if completed_clones:
            parent.status = UniversalStatus.COMPLETED
            return True

        # Parent fails if all clones fail
        if failed_clones and len(failed_clones) == len(parent.child_task_ids):
            parent.status = UniversalStatus.FAILED
            return True

        return False

    def check_subtask_completion(self, parent_id: str) -> bool:
        """Check if parent task can complete based on subtask completion rules.

        Per AGENT_ENGINE_SPEC §2.1: Parent completes when ALL subtasks succeed.
        Per Phase 7: If some subtasks fail but not all, parent enters PARTIAL.

        Args:
            parent_id: Parent task ID

        Returns:
            True if all subtasks have reached terminal state, False otherwise
        """
        parent = self.tasks.get(parent_id)
        if not parent or not parent.child_task_ids:
            return False

        completed_subtasks = []
        failed_subtasks = []

        for child_id in parent.child_task_ids:
            child = self.tasks.get(child_id)
            if child and child.lineage_type == "subtask":
                if child.status == UniversalStatus.COMPLETED:
                    completed_subtasks.append(child)
                elif child.status == UniversalStatus.FAILED:
                    failed_subtasks.append(child)
                else:
                    return False  # Still have pending subtasks

        # All subtasks terminal - determine parent status
        total = len(parent.child_task_ids)

        if len(completed_subtasks) == total:
            # All succeeded
            parent.status = UniversalStatus.COMPLETED
            return True
        elif len(failed_subtasks) == total:
            # All failed
            parent.status = UniversalStatus.FAILED
            return True
        else:
            # Mixed success/failure
            parent.status = UniversalStatus.PARTIAL
            return True

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

        Reads only required fields: task_id, status, timestamps.
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
            "created_at": task_data.get("created_at"),
            "updated_at": task_data.get("updated_at")
        }

        return metadata, None

    def update_task_status(self, task_id: str, status: UniversalStatus) -> None:
        """Update task status.

        Per Phase 7, centralizes task status updates for observability and consistency.

        Args:
            task_id: Task to update
            status: New status value
        """
        task = self.tasks.get(task_id)
        if task:
            task.status = status
            task.updated_at = _now_iso()

    def update_task_lifecycle(self, task_id: str, lifecycle: TaskLifecycle) -> None:
        """Update task lifecycle.

        Per Phase 7, centralizes task lifecycle updates.

        Args:
            task_id: Task to update
            lifecycle: New lifecycle value
        """
        task = self.tasks.get(task_id)
        if task:
            task.lifecycle = lifecycle
            task.updated_at = _now_iso()

    def update_task_output(self, task_id: str, output: Any) -> None:
        """Update task current output.

        Per Phase 7, centralizes task output updates.

        Args:
            task_id: Task to update
            output: New output value
        """
        task = self.tasks.get(task_id)
        if task:
            task.current_output = output
            task.updated_at = _now_iso()
