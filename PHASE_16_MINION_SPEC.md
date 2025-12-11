# Phase 16: Inspector Mode - MINIMAL IMPLEMENTATION

## Goal
Basic inspection API for replaying task history and artifacts.

## Minimal Scope (Phase 16 v1)
- Inspector class for reading task history
- Query artifacts by task
- Replay telemetry events
- **NO interactive stepping** (future work)
- **NO state mutation** (future work)
- **NO pause/resume** (future work)

## Implementation

### 1. Inspector Class (`src/agent_engine/runtime/inspector.py`)
```python
from typing import List, Optional, Dict, Any
from agent_engine.schemas import Task, Event, ArtifactRecord

class Inspector:
    """Read-only inspector for task history, artifacts, and telemetry."""

    def __init__(self, task_manager, artifact_store, telemetry):
        self.task_manager = task_manager
        self.artifact_store = artifact_store
        self.telemetry = telemetry

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID."""
        return self.task_manager.get_task(task_id)

    def get_task_history(self, task_id: str) -> List[Any]:
        """Get execution history for task."""
        task = self.get_task(task_id)
        return task.history if task else []

    def get_task_artifacts(self, task_id: str) -> List[ArtifactRecord]:
        """Get all artifacts for task."""
        if not self.artifact_store:
            return []
        return self.artifact_store.get_artifacts_by_task(task_id)

    def get_task_events(self, task_id: str) -> List[Event]:
        """Get telemetry events for task."""
        all_events = self.telemetry.events
        return [e for e in all_events if e.task_id == task_id]

    def get_task_summary(self, task_id: str) -> Dict[str, Any]:
        """Get summary of task execution."""
        task = self.get_task(task_id)
        if not task:
            return {}

        return {
            "task_id": task_id,
            "status": task.status.value if task.status else "unknown",
            "lifecycle": task.lifecycle.value if task.lifecycle else "unknown",
            "history_count": len(task.history),
            "artifact_count": len(self.get_task_artifacts(task_id)),
            "event_count": len(self.get_task_events(task_id))
        }
```

### 2. Engine Integration
```python
# In src/agent_engine/engine.py
def create_inspector(self):
    """Create an inspector for examining task execution."""
    from agent_engine.runtime import Inspector
    return Inspector(
        task_manager=self.task_manager,
        artifact_store=self.artifact_store,
        telemetry=self.telemetry
    )
```

### 3. Tests (12 tests minimum)
- Inspector creation (1)
- get_task tests (2)
- get_task_history tests (2)
- get_task_artifacts tests (2)
- get_task_events tests (2)
- get_task_summary tests (3)

## Files to Create
- src/agent_engine/runtime/inspector.py
- tests/test_phase16_inspector.py

## Files to Modify
- src/agent_engine/runtime/__init__.py (export Inspector)
- src/agent_engine/engine.py (add create_inspector)

## Success Criteria
✅ Inspector can query task history
✅ Inspector can query artifacts
✅ Inspector can query events
✅ 12+ tests passing
✅ No regressions
