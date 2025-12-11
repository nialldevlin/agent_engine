# Phase 17: Multi-Task Execution - MINIMAL IMPLEMENTATION

## Goal
Support for tracking multiple tasks with isolated state.

## Minimal Scope (Phase 17 v1)
- TaskManager already supports multiple tasks
- Add task listing/querying methods
- Document isolation guarantees
- **NO concurrent execution** (sequential only)
- **NO task scheduling** (future work)
- **NO execution.yaml** (future work)

## Implementation

### 1. TaskManager Enhancements
```python
# In src/agent_engine/runtime/task_manager.py
# Add methods for multi-task queries:

def get_all_tasks(self) -> List[Task]:
    """Get all tasks."""
    return list(self.tasks.values())

def get_tasks_by_status(self, status: UniversalStatus) -> List[Task]:
    """Get tasks with specific status."""
    return [t for t in self.tasks.values() if t.status == status]

def get_task_count(self) -> int:
    """Get total number of tasks."""
    return len(self.tasks)

def clear_completed_tasks(self) -> int:
    """Remove completed tasks from memory. Returns count removed."""
    completed = [tid for tid, t in self.tasks.items()
                 if t.lifecycle == TaskLifecycle.COMPLETED]
    for tid in completed:
        del self.tasks[tid]
    return len(completed)
```

### 2. Engine Multi-Task Support
```python
# In src/agent_engine/engine.py
def run_multiple(self, inputs: List[Any], start_node_id: Optional[str] = None) -> List[Dict]:
    """Run multiple tasks sequentially.

    Each task gets isolated state (separate task_id, history, memory).
    Returns list of task results in same order as inputs.
    """
    results = []
    for input_data in inputs:
        result = self.run(input_data, start_node_id)
        results.append(result)
    return results

def get_all_task_ids(self) -> List[str]:
    """Get all task IDs."""
    return list(self.task_manager.tasks.keys())

def get_task_summary(self, task_id: str) -> Optional[Dict]:
    """Get summary for a specific task."""
    task = self.task_manager.get_task(task_id)
    if not task:
        return None
    return {
        "task_id": task_id,
        "status": task.status.value if task.status else "unknown",
        "lifecycle": task.lifecycle.value if task.lifecycle else "unknown",
        "spec": task.spec
    }
```

### 3. Documentation
Create docs/MULTI_TASK_ISOLATION.md explaining:
- Each task has unique task_id
- Task-level memory is isolated
- History is per-task
- Artifacts tagged with task_id
- Telemetry events tagged with task_id
- No shared mutable state between tasks

### 4. Tests (15 tests minimum)
- TaskManager multi-task tests (5)
- Engine.run_multiple tests (5)
- Isolation tests (5): verify separate memory, history, artifacts

## Files to Create
- docs/MULTI_TASK_ISOLATION.md
- tests/test_phase17_multitask.py

## Files to Modify
- src/agent_engine/runtime/task_manager.py (add query methods)
- src/agent_engine/engine.py (add run_multiple, get_all_task_ids, get_task_summary)

## Success Criteria
✅ Multiple tasks tracked with unique IDs
✅ Task isolation documented and tested
✅ Engine.run_multiple() works sequentially
✅ 15+ tests passing
✅ No regressions
