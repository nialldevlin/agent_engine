# PHASE_8_IMPLEMENTATION_PLAN.md

## SECTION 1 — Phase Summary

**Phase 8: Telemetry & Event Bus**

This phase completes the observability infrastructure per AGENT_ENGINE_SPEC §6 and AGENT_ENGINE_OVERVIEW §5.

**Goal**: Provide comprehensive event emission for all major engine actions, enabling introspection, debugging, and plugin integration.

**Key Components**:
1. **Event Bus Enhancement**: Expand TelemetryBus with structured event methods
2. **Task Events**: Task start/end/creation
3. **Node Events**: Node start/end with detailed payloads
4. **Routing Events**: Routing decisions, branch/split/merge operations
5. **Tool Events**: Tool invocations and results
6. **Context Events**: Context assembly operations
7. **Clone/Subtask Events**: Child task creation
8. **Integration**: Add event emission to Router and NodeExecutor

**Scope**: Complete event emission for all engine operations. Event consumers (plugins) are Phase 9.

---

## SECTION 2 — Requirements & Invariants

### 2.1 Canonical Requirements

Per AGENT_ENGINE_SPEC §6 (Observability Requirements):

The engine must capture:
- Every node input/output pair
- Context used at each stage
- Tool invocations
- Routing decisions
- Merge events
- Clone/subtask creation
- Timestamps
- Structured status metadata

The engine must support:
- Replayability
- Deterministic debug traces
- Optional telemetry sinks (plugins)

Per AGENT_ENGINE_OVERVIEW §5 (Observability & Telemetry):

- **Execution Trace** (§5.1): Complete record of Task journey through DAG with structured entries
- **Logs & Metrics** (§5.2): Structured logging of validation failures, context assembly, tool execution, LLM usage, node performance
- **Replayability** (§5.3): Deterministic replay capability

### 2.2 Current State Analysis

**Already Implemented**:
- Basic TelemetryBus class with event list storage
- Event schema (Event, EventType enum)
- Some events in DAGExecutor: task start, stage start/end
- _emit_event helper method in DAGExecutor

**Missing (Phase 8 Must Implement)**:
- Structured event emission methods on TelemetryBus
- Task end/complete events
- Routing decision events
- Tool invocation events
- Context assembly events
- Clone/subtask creation events
- Event emission in Router
- Event emission in NodeExecutor
- Timestamps on all events
- Comprehensive event payloads

### 2.3 Event Types & Payloads

Per requirements, the following events must be emitted:

1. **Task Events**:
   - `task_started`: task_id, spec, mode, timestamp
   - `task_completed`: task_id, status, lifecycle, output, timestamp
   - `task_failed`: task_id, error, timestamp

2. **Node Events**:
   - `node_started`: task_id, node_id, role, kind, input, timestamp
   - `node_completed`: task_id, node_id, output, status, timestamp
   - `node_failed`: task_id, node_id, error, timestamp

3. **Routing Events**:
   - `routing_decision`: task_id, node_id, decision, next_node_id, timestamp
   - `routing_branch`: task_id, node_id, clone_count, clone_ids, timestamp
   - `routing_split`: task_id, node_id, subtask_count, subtask_ids, timestamp
   - `routing_merge`: task_id, node_id, input_count, input_statuses, timestamp

4. **Tool Events**:
   - `tool_invoked`: task_id, node_id, tool_id, inputs, timestamp
   - `tool_completed`: task_id, node_id, tool_id, output, status, timestamp
   - `tool_failed`: task_id, node_id, tool_id, error, timestamp

5. **Context Events**:
   - `context_assembled`: task_id, node_id, profile_id, item_count, token_count, timestamp
   - `context_failed`: task_id, node_id, error, timestamp

6. **Clone/Subtask Events**:
   - `clone_created`: parent_task_id, clone_id, node_id, lineage, timestamp
   - `subtask_created`: parent_task_id, subtask_id, node_id, lineage, timestamp

### 2.4 Invariants

1. **Event Immutability**: Events are immutable once emitted
2. **Event Ordering**: Events emitted in execution order
3. **Event Completeness**: All major actions produce events
4. **Timestamp Consistency**: All events have ISO-8601 timestamps
5. **Payload Structure**: All events have structured, serializable payloads
6. **No Side Effects**: Event emission never affects execution flow
7. **Determinism**: Same execution → same event sequence (modulo timestamps)

---

## SECTION 3 — LLM Implementation Plan

### Step 1: Enhance TelemetryBus with Structured Event Methods

**File**: `src/agent_engine/telemetry.py`

**Changes**:

1. Add timestamp helper:
   ```python
   from datetime import datetime
   from zoneinfo import ZoneInfo

   def _now_iso() -> str:
       """Generate ISO-8601 timestamp."""
       return datetime.now(ZoneInfo("UTC")).isoformat()
   ```

2. Add task event methods:
   ```python
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
   ```

3. Add node event methods:
   ```python
   def node_started(self, task_id: str, node_id: str, role: str, kind: str, input_data: Any) -> None:
       """Emit node started event."""
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

   def node_completed(self, task_id: str, node_id: str, output: Any, status: str) -> None:
       """Emit node completed event."""
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
   ```

4. Add routing event methods:
   ```python
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
   ```

5. Add tool event methods:
   ```python
   def tool_invoked(self, task_id: str, node_id: str, tool_id: str, inputs: Any) -> None:
       """Emit tool invoked event."""
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

   def tool_completed(self, task_id: str, node_id: str, tool_id: str, output: Any, status: str) -> None:
       """Emit tool completed event."""
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
   ```

6. Add context event methods:
   ```python
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
   ```

7. Add clone/subtask event methods:
   ```python
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
   ```

---

### Step 2: Add Event Emission to Router

**File**: `src/agent_engine/runtime/router.py`

**Changes**:

1. Add telemetry to Router __init__:
   ```python
   def __init__(self, dag: DAG, task_manager, node_executor, telemetry=None):
       """Initialize router with DAG and runtime dependencies."""
       self.dag = dag
       self.task_manager = task_manager
       self.node_executor = node_executor
       self.telemetry = telemetry  # NEW
       # ... rest of init
   ```

2. Emit routing decision events in `_route_linear`:
   ```python
   def _route_linear(self, task: Task, node: Node, output: Any) -> Optional[str]:
       """Route through linear node (single outbound)."""
       edges = self.dag.adjacency_map.get(node.stage_id, [])
       if not edges:
           return None

       next_node_id = edges[0]

       # Emit routing decision event
       if self.telemetry:
           self.telemetry.routing_decision(
               task_id=task.task_id,
               node_id=node.stage_id,
               decision="linear",
               next_node_id=next_node_id
           )

       return next_node_id
   ```

3. Emit routing decision events in `_route_decision`:
   ```python
   def _route_decision(self, task: Task, node: Node, output: Any) -> Optional[str]:
       """Route through decision node (select one outbound edge)."""
       # ... existing logic to extract selected_edge_label ...

       # Emit routing decision event
       if self.telemetry:
           self.telemetry.routing_decision(
               task_id=task.task_id,
               node_id=node.stage_id,
               decision=selected_edge_label,
               next_node_id=next_node_id
           )

       return next_node_id
   ```

4. Emit branch events in `_route_branch`:
   ```python
   def _route_branch(self, task: Task, node: Node) -> None:
       """Route through branch node (create clones)."""
       edges = self.dag.adjacency_map.get(node.stage_id, [])
       clone_ids = []

       for edge_label in edges:
           clone = self.task_manager.create_clone(
               parent_task_id=task.task_id,
               branch_label=edge_label,
               stage_id=node.stage_id,
               clone_index=len(clone_ids)
           )
           clone_ids.append(clone.task_id)
           self._enqueue_work(clone.task_id, edge_label)

       # Emit branch event
       if self.telemetry:
           self.telemetry.routing_branch(
               task_id=task.task_id,
               node_id=node.stage_id,
               clone_count=len(clone_ids),
               clone_ids=clone_ids
           )

       # Emit clone created events
       if self.telemetry:
           for clone_id in clone_ids:
               clone = self.task_manager.get_task(clone_id)
               if clone and clone.lineage:
                   self.telemetry.clone_created(
                       parent_task_id=task.task_id,
                       clone_id=clone_id,
                       node_id=node.stage_id,
                       lineage=clone.lineage
                   )
   ```

5. Emit split events in `_route_split`:
   ```python
   def _route_split(self, task: Task, node: Node, output: Any) -> None:
       """Route through split node (create subtasks)."""
       edges = self.dag.adjacency_map.get(node.stage_id, [])
       subtask_ids = []

       # ... existing subtask creation logic ...

       # Emit split event
       if self.telemetry:
           self.telemetry.routing_split(
               task_id=task.task_id,
               node_id=node.stage_id,
               subtask_count=len(subtask_ids),
               subtask_ids=subtask_ids
           )

       # Emit subtask created events
       if self.telemetry:
           for subtask_id in subtask_ids:
               subtask = self.task_manager.get_task(subtask_id)
               if subtask and subtask.lineage:
                   self.telemetry.subtask_created(
                       parent_task_id=task.task_id,
                       subtask_id=subtask_id,
                       node_id=node.stage_id,
                       lineage=subtask.lineage
                   )
   ```

6. Emit merge events in `_route_merge`:
   ```python
   def _route_merge(self, task: Task, node: Node) -> Optional[str]:
       """Route through merge node (wait for all inputs)."""
       # ... existing merge logic to collect inputs ...

       input_statuses = [inp.status.value for inp in merge_inputs]

       # Emit merge event
       if self.telemetry:
           self.telemetry.routing_merge(
               task_id=task.task_id,
               node_id=node.stage_id,
               input_count=len(merge_inputs),
               input_statuses=input_statuses
           )

       # ... rest of merge logic ...
   ```

---

### Step 3: Add Event Emission to NodeExecutor

**File**: `src/agent_engine/runtime/node_executor.py`

**Changes**:

1. Add telemetry to NodeExecutor __init__:
   ```python
   def __init__(
       self,
       agent_runtime,
       tool_runtime,
       context_assembler,
       json_engine,
       deterministic_registry,
       context_profiles,
       telemetry=None  # NEW
   ):
       # ... existing init ...
       self.telemetry = telemetry
   ```

2. Emit node start event at beginning of execute_node:
   ```python
   def execute_node(self, task: Task, node: Node) -> Tuple[StageExecutionRecord, Optional[Any]]:
       """Execute a single node following canonical lifecycle."""
       started_at = _now_iso()

       # Emit node started event
       if self.telemetry:
           self.telemetry.node_started(
               task_id=task.task_id,
               node_id=node.stage_id,
               role=node.role.value,
               kind=node.kind.value,
               input_data=task.current_output
           )

       # ... rest of execution
   ```

3. Emit node complete/failed events at end of execute_node:
   ```python
   # Before returning success record:
   if self.telemetry:
       self.telemetry.node_completed(
           task_id=task.task_id,
           node_id=node.stage_id,
           output=output,
           status=record.node_status.value
       )

   return record, output

   # In error paths, before returning error record:
   if self.telemetry:
       self.telemetry.node_failed(
           task_id=task.task_id,
           node_id=node.stage_id,
           error=error
       )
   ```

4. Emit context assembly events:
   ```python
   # After successful context assembly:
   if self.telemetry and context_package:
       item_count = len(context_package.items) if hasattr(context_package, 'items') else 0
       token_count = sum(i.token_cost or 0 for i in context_package.items) if hasattr(context_package, 'items') else 0

       self.telemetry.context_assembled(
           task_id=task.task_id,
           node_id=node.stage_id,
           profile_id=context_profile_id or "none",
           item_count=item_count,
           token_count=token_count
       )

   # In context assembly error handler:
   if self.telemetry:
       self.telemetry.context_failed(
           task_id=task.task_id,
           node_id=node.stage_id,
           error=error
       )
   ```

---

### Step 4: Add Event Emission to ToolRuntime (if exists)

**File**: `src/agent_engine/runtime/tool_runtime.py`

**Check if file exists and has tool execution logic. If so:**

1. Add telemetry parameter to __init__
2. Emit tool_invoked before tool execution
3. Emit tool_completed or tool_failed after tool execution

**Example**:
```python
def execute_tool(self, task_id: str, node_id: str, tool_id: str, inputs: Any) -> Any:
    """Execute a tool."""

    # Emit tool invoked event
    if self.telemetry:
        self.telemetry.tool_invoked(
            task_id=task_id,
            node_id=node_id,
            tool_id=tool_id,
            inputs=inputs
        )

    try:
        # Execute tool
        output = self._execute_tool_internal(tool_id, inputs)

        # Emit tool completed event
        if self.telemetry:
            self.telemetry.tool_completed(
                task_id=task_id,
                node_id=node_id,
                tool_id=tool_id,
                output=output,
                status="success"
            )

        return output

    except Exception as e:
        # Emit tool failed event
        if self.telemetry:
            self.telemetry.tool_failed(
                task_id=task_id,
                node_id=node_id,
                tool_id=tool_id,
                error=e
            )
        raise
```

---

### Step 5: Update Engine to Pass Telemetry to Components

**File**: `src/agent_engine/engine.py`

**Changes**:

1. Create TelemetryBus instance in Engine.__init__:
   ```python
   from .telemetry import TelemetryBus

   def __init__(self, ...):
       # ... existing init ...

       # Initialize telemetry (Phase 8)
       self.telemetry = TelemetryBus()
   ```

2. Pass telemetry to NodeExecutor:
   ```python
   self.node_executor = NodeExecutor(
       agent_runtime=self.agent_runtime,
       tool_runtime=self.tool_runtime,
       context_assembler=self.context_assembler,
       json_engine=...,
       deterministic_registry=self.deterministic_registry,
       context_profiles=self.context_profiles,
       telemetry=self.telemetry  # NEW
   )
   ```

3. Pass telemetry to Router:
   ```python
   self.router = Router(
       dag=self.dag,
       task_manager=self.task_manager,
       node_executor=self.node_executor,
       telemetry=self.telemetry  # NEW
   )
   ```

4. Pass telemetry to ToolRuntime (if it exists and needs it):
   ```python
   self.tool_runtime = ToolRuntime(
       tools=...,
       telemetry=self.telemetry  # NEW if applicable
   )
   ```

---

### Step 6: Update DAGExecutor to Use Enhanced Telemetry

**File**: `src/agent_engine/runtime/dag_executor.py`

**Changes**:

1. Replace existing _emit_event calls with new telemetry methods:
   ```python
   # Before task execution:
   if self.telemetry:
       self.telemetry.task_started(
           task_id=task.task_id,
           spec=task.spec,
           mode=task.spec.mode.value if hasattr(task.spec, 'mode') else "unknown"
       )

   # After successful task completion:
   if self.telemetry:
       self.telemetry.task_completed(
           task_id=task.task_id,
           status=task.status.value,
           lifecycle=task.lifecycle.value,
           output=task.current_output
       )

   # After task failure:
   if self.telemetry:
       self.telemetry.task_failed(
           task_id=task.task_id,
           error=error
       )
   ```

2. Remove old _emit_event method or update it to delegate to new methods

---

### Step 7: Add Telemetry Access Methods to Engine

**File**: `src/agent_engine/engine.py`

**Add methods** for accessing telemetry:

```python
def get_events(self) -> List[Event]:
    """Get all telemetry events.

    Returns:
        List of Event objects in emission order
    """
    return self.telemetry.events.copy()

def get_events_by_type(self, event_type: EventType) -> List[Event]:
    """Get events filtered by type.

    Args:
        event_type: EventType to filter by

    Returns:
        List of matching Event objects
    """
    return [e for e in self.telemetry.events if e.type == event_type]

def get_events_by_task(self, task_id: str) -> List[Event]:
    """Get events for a specific task.

    Args:
        task_id: Task ID to filter by

    Returns:
        List of Event objects for this task
    """
    return [e for e in self.telemetry.events if e.task_id == task_id]

def clear_events(self) -> None:
    """Clear all telemetry events."""
    self.telemetry.events.clear()
```

---

### Step 8: Create Comprehensive Tests

**Create**: `tests/test_phase8_telemetry.py`

**Test Coverage** (minimum 30 tests):

1. **TelemetryBus Methods** (10 tests):
   - Test task_started event structure
   - Test task_completed event structure
   - Test task_failed event structure
   - Test node_started/completed/failed events
   - Test routing events (decision, branch, split, merge)
   - Test tool events (invoked, completed, failed)
   - Test context events (assembled, failed)
   - Test clone/subtask created events
   - Test event ordering
   - Test event timestamps

2. **Event Emission in Router** (8 tests):
   - Test routing_decision emitted for LINEAR nodes
   - Test routing_decision emitted for DECISION nodes
   - Test routing_branch emitted for BRANCH nodes
   - Test clone_created events for each clone
   - Test routing_split emitted for SPLIT nodes
   - Test subtask_created events for each subtask
   - Test routing_merge emitted for MERGE nodes
   - Test event payload correctness

3. **Event Emission in NodeExecutor** (6 tests):
   - Test node_started emitted before execution
   - Test node_completed emitted on success
   - Test node_failed emitted on error
   - Test context_assembled emitted after context assembly
   - Test context_failed emitted on context error
   - Test event payloads contain correct data

4. **Integration Tests** (6 tests):
   - Test simple linear workflow produces complete event trace
   - Test decision workflow produces routing decision events
   - Test branch workflow produces clone events
   - Test split workflow produces subtask events
   - Test merge workflow produces merge events
   - Test error handling produces error events
   - Test event count matches execution path
   - Test events retrievable via Engine methods

**Update Existing Tests**:
- Ensure all Phase 1-7 tests still pass with telemetry enabled
- No regressions in execution behavior

---

### Step 9: Update Documentation

**File**: `README.md`

**Add Phase 8 section**:

1. Telemetry & Event Bus overview
2. Event types and payloads reference
3. How to access telemetry events
4. Example: Inspecting execution trace
5. Example: Filtering events by type/task
6. Telemetry for debugging and observability

**File**: `docs/operational/PLAN_BUILD_AGENT_ENGINE.md`

**Update Phase 8 status**:
- Mark as "✅ COMPLETE"
- Add summary of changes
- Add acceptance criteria checklist

---

## SECTION 4 — Acceptance Criteria

Phase 8 is complete when ALL of the following are verified:

### 4.1 TelemetryBus Enhancement

- [ ] TelemetryBus has all required event emission methods (14+ methods)
- [ ] All events have ISO-8601 timestamps
- [ ] All events have structured, serializable payloads
- [ ] Event IDs are unique and sequential
- [ ] Events stored in emission order

### 4.2 Task Events

- [ ] task_started emitted when task begins
- [ ] task_completed emitted when task succeeds
- [ ] task_failed emitted when task fails
- [ ] Task events include: task_id, spec, mode, status, lifecycle

### 4.3 Node Events

- [ ] node_started emitted before each node execution
- [ ] node_completed emitted after successful node execution
- [ ] node_failed emitted after failed node execution
- [ ] Node events include: task_id, node_id, role, kind, input, output, status

### 4.4 Routing Events

- [ ] routing_decision emitted for LINEAR and DECISION nodes
- [ ] routing_branch emitted for BRANCH nodes
- [ ] routing_split emitted for SPLIT nodes
- [ ] routing_merge emitted for MERGE nodes
- [ ] Routing events include correct next_node_id or child task IDs

### 4.5 Tool Events

- [ ] tool_invoked emitted before tool execution
- [ ] tool_completed emitted after successful tool execution
- [ ] tool_failed emitted after failed tool execution
- [ ] Tool events include: task_id, node_id, tool_id, inputs, output

### 4.6 Context Events

- [ ] context_assembled emitted after successful context assembly
- [ ] context_failed emitted on context assembly error
- [ ] Context events include: profile_id, item_count, token_count

### 4.7 Clone/Subtask Events

- [ ] clone_created emitted for each clone in BRANCH
- [ ] subtask_created emitted for each subtask in SPLIT
- [ ] Events include lineage information

### 4.8 Integration

- [ ] Router receives and uses telemetry instance
- [ ] NodeExecutor receives and uses telemetry instance
- [ ] ToolRuntime receives and uses telemetry instance (if applicable)
- [ ] Engine creates and passes telemetry to all components
- [ ] No circular dependencies

### 4.9 Event Access

- [ ] Engine.get_events() returns all events
- [ ] Engine.get_events_by_type() filters correctly
- [ ] Engine.get_events_by_task() filters correctly
- [ ] Engine.clear_events() clears event list

### 4.10 Test Coverage

- [ ] At least 30 new Phase 8 tests added
- [ ] All event emission scenarios covered
- [ ] All event payload structures validated
- [ ] Integration tests verify complete event traces
- [ ] All tests passing (635 existing + 30 new = 665 minimum)

### 4.11 Documentation

- [ ] README.md updated with Phase 8 section
- [ ] Event types and payloads documented
- [ ] Event access methods documented
- [ ] Example code for telemetry usage provided

### 4.12 No Regressions

- [ ] All Phase 1-7 tests still passing
- [ ] No breaking changes to existing APIs
- [ ] Event emission does not affect execution flow
- [ ] Deterministic execution preserved

---

## SECTION 5 — Clarifying Questions

**None.**

All required information is present in canonical specifications. Phase 8 can be implemented deterministically following this plan.
