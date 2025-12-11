# PHASE_7_IMPLEMENTATION_PLAN.md

## SECTION 1 — Phase Summary

**Phase 7: Error Handling, Status Propagation & Exit Behavior**

This phase implements canonical error handling and status propagation semantics per AGENT_ENGINE_SPEC §3.4, §3.5, §7, and AGENT_ENGINE_OVERVIEW §6.

**Goal**: Ensure all error handling, status propagation, and exit node behavior follows canonical specifications exactly.

**Key Components**:
1. **PARTIAL status**: Add missing status value to UniversalStatus enum
2. **Node-level failure logic**: Implement `continue_on_failure` behavior
3. **Task-level status propagation**: Success/failure/partial propagation through DAG
4. **Merge node failure handling**: Configure how merges handle upstream failures
5. **Exit node validation**: Enforce deterministic, read-only, no-agent/no-tool constraints
6. **Exit node `always_fail` flag**: Override task status to FAILED at error exits
7. **Pre-exit status requirement**: Validate task status is set before reaching exit

**Scope**: Complete error handling and status propagation per canonical specs. No additional error recovery mechanisms beyond what's specified.

---

## SECTION 2 — Requirements & Invariants

### 2.1 Canonical Requirements

Per AGENT_ENGINE_SPEC §3.4 (Status Propagation):

1. **Universal Status Model**:
   - All entities (tasks, nodes, tools, clones, subtasks) use: `success | failure | partial`
   - Implementation mapping:
     - `success` → `UniversalStatus.COMPLETED`
     - `failure` → `UniversalStatus.FAILED`
     - `partial` → `UniversalStatus.PARTIAL` (NEW)

2. **Status Propagation Rules**:
   - Tools report status → node inherits if misuse
   - Errors NOT caused by misuse do not automatically change node status
   - Node status must be set explicitly
   - Merge nodes may ignore or consider failure metadata based on configuration
   - Task status must be set *before* reaching an exit node
   - Exit nodes never determine correctness; they only present already-decided status

3. **Failure Handling** (SPEC §3.5):
   - Nodes may specify:
     - `continue_on_failure: true` → execution continues despite node failure
     - `continue_on_failure: false` (default) → execution stops on node failure
   - Branch, split, and merge nodes may incorporate failure logic defined per node

4. **Exit Node Constraints** (SPEC §3.1, role EXIT):
   - Deterministic only (kind must be DETERMINISTIC)
   - Read-only behavior (cannot modify task state)
   - Cannot invoke agents or tools
   - Returns output to user using task's pre-set status
   - May be flagged `always_fail` to override status to FAILED

Per AGENT_ENGINE_SPEC §7 (Error Semantics):

5. **Stage Errors** (§7.1):
   - Stage may fail due to: schema mismatch, invalid routing decision, context assembly failure, tool misuse
   - Stage failure recorded in task history with structured metadata

6. **Task Errors** (§7.2):
   - Task enters `partial` when some subtasks or clones fail but parent rules allow partial completion
   - Task enters `failure` when unrecoverable error occurs

7. **Exit Errors** (§7.3):
   - Exit nodes marked `always_fail` override any existing success to failure

### 2.2 Current State Analysis

**Already Implemented**:
- UniversalStatus enum with PENDING, IN_PROGRESS, COMPLETED, FAILED, CANCELLED, BLOCKED
- Node.continue_on_failure field in schema
- Error recording in StageExecutionRecord
- Basic node execution with error returns

**Missing (Phase 7 Must Implement)**:
- PARTIAL status value
- continue_on_failure enforcement in execution flow
- Task status propagation logic
- Merge node failure handling
- Exit node validation (no agents, no tools, deterministic only)
- Exit node always_fail flag and behavior
- Pre-exit status validation

### 2.3 Invariants

1. **Status Consistency**: Task.status must be one of COMPLETED, FAILED, PARTIAL
2. **Exit Node Determinism**: All EXIT nodes must have kind=DETERMINISTIC
3. **Exit Node Read-Only**: Exit nodes cannot modify task.current_output (only format/return)
4. **Exit Node Tool Restriction**: Exit nodes cannot call tools or agents
5. **Pre-Exit Status**: Task.status must be set before router reaches exit node
6. **continue_on_failure Semantics**: When true, node failure doesn't stop execution; task continues to next node
7. **Partial Status Semantics**: Task status=PARTIAL when some children fail but not all (merge recombination)

---

## SECTION 3 — LLM Implementation Plan

### Step 1: Add PARTIAL Status to UniversalStatus Enum

**File**: `src/agent_engine/schemas/task.py`

**Changes**:

1. Add PARTIAL to UniversalStatus enum:
   ```python
   class UniversalStatus(str, Enum):
       """..."""
       PENDING = "pending"
       IN_PROGRESS = "in_progress"
       COMPLETED = "completed"
       FAILED = "failed"
       PARTIAL = "partial"  # NEW
       CANCELLED = "cancelled"
       BLOCKED = "blocked"
   ```

2. Update docstring to include PARTIAL:
   ```
   Status Values:
   - PENDING: Waiting to start or continue execution.
   - IN_PROGRESS: Currently executing (actively being processed).
   - COMPLETED: Finished successfully (all work done, no errors).
   - FAILED: Finished with unrecoverable error.
   - PARTIAL: Finished with partial success (some children failed, some succeeded).
   - CANCELLED: Explicitly halted before normal completion.
   - BLOCKED: Cannot proceed due to unmet dependency or resource constraint.
   ```

3. Update status propagation documentation in docstring:
   ```
   Partial Status Semantics:
   - Task enters PARTIAL when some subtasks/clones fail but parent allows continuation.
   - Merge nodes may produce PARTIAL status when recombining mixed success/failure results.
   - PARTIAL is distinct from FAILED: some work succeeded, some did not.
   ```

**Why**: Canonical spec requires "success | failure | partial", but current implementation only has COMPLETED and FAILED.

---

### Step 2: Add `always_fail` Flag to Node Schema

**File**: `src/agent_engine/schemas/stage.py`

**Changes**:

1. Add `always_fail` field to Node class:
   ```python
   always_fail: bool = Field(
       default=False,
       description="If True (EXIT nodes only), override task status to FAILED"
   )
   ```

2. Update Node docstring:
   ```
   always_fail: For EXIT nodes only. If True, overrides task.status to FAILED
                regardless of current status. Used for error exit nodes that
                should always report failure.
   ```

**Why**: Per SPEC §7.3, exit nodes may be flagged `always_fail` to override success.

---

### Step 3: Implement Exit Node Validation

**File**: `src/agent_engine/schema_validator.py`

**Add exit node validation** in `validate_dag` or `validate_workflow`:

```python
def validate_exit_nodes(dag: DAG) -> None:
    """Validate exit node constraints per AGENT_ENGINE_SPEC §3.1.

    Exit node requirements:
    - Must have kind=DETERMINISTIC (cannot be AGENT)
    - Must have 0 outbound edges
    - Must have ≥1 inbound edges
    - Cannot specify tools (tools list must be empty)
    - always_fail flag only meaningful for EXIT nodes

    Raises:
        SchemaValidationError: If exit node violates constraints
    """
    for node in dag.nodes.values():
        if node.role == NodeRole.EXIT:
            # Must be deterministic
            if node.kind != NodeKind.DETERMINISTIC:
                raise SchemaValidationError(
                    f"Exit node {node.stage_id}: must be DETERMINISTIC (cannot be AGENT)"
                )

            # Cannot have tools
            if node.tools:
                raise SchemaValidationError(
                    f"Exit node {node.stage_id}: cannot specify tools (must be read-only)"
                )

            # Must have ≥1 inbound edges
            inbound = dag.get_inbound_edges(node.stage_id)
            if not inbound:
                raise SchemaValidationError(
                    f"Exit node {node.stage_id}: must have at least 1 inbound edge"
                )

            # Must have 0 outbound edges
            outbound = dag.adjacency_map.get(node.stage_id, [])
            if outbound:
                raise SchemaValidationError(
                    f"Exit node {node.stage_id}: cannot have outbound edges"
                )

        else:
            # always_fail only valid for EXIT nodes
            if node.always_fail:
                raise SchemaValidationError(
                    f"Node {node.stage_id}: always_fail=True only valid for EXIT nodes"
                )
```

**File**: `src/agent_engine/engine.py`

**Call validation** after DAG construction:

```python
from .schema_validator import validate_exit_nodes

# In Engine.from_config_dir(), after DAG creation:
validate_exit_nodes(dag)
```

---

### Step 4: Enforce Read-Only Exit Node Behavior

**File**: `src/agent_engine/runtime/deterministic_registry.py`

**Update default EXIT implementation** to be strictly read-only:

```python
def _default_exit(task: Task, node: Node) -> Any:
    """Default EXIT node: read-only identity transform.

    Per AGENT_ENGINE_SPEC §3.1:
    - Exit nodes are read-only
    - Cannot modify task state
    - Cannot invoke agents or tools
    - Simply format and return current output

    Returns:
        task.current_output (unmodified)
    """
    # Read-only: return current output as-is
    # Do NOT modify task.current_output
    # Do NOT call any tools or agents
    return task.current_output
```

**Add validation** in NodeExecutor when executing EXIT nodes:

**File**: `src/agent_engine/runtime/node_executor.py`

```python
def execute_node(self, task: Task, node: Node) -> Tuple[StageExecutionRecord, Optional[Any]]:
    """..."""

    # Validate EXIT node constraints before execution
    if node.role == NodeRole.EXIT:
        self._validate_exit_node_execution(task, node)

    # ... rest of execution
```

```python
def _validate_exit_node_execution(self, task: Task, node: Node) -> None:
    """Validate exit node execution constraints.

    Per AGENT_ENGINE_SPEC §3.1:
    - Exit nodes must be deterministic
    - Cannot invoke agents or tools
    - Task status must be set before reaching exit

    Raises:
        EngineError: If exit node violates constraints
    """
    # Must be deterministic (already validated at DAG load, but double-check)
    if node.kind != NodeKind.DETERMINISTIC:
        raise EngineError(
            error_id="exit_node_agent_error",
            code=EngineErrorCode.INVALID_NODE,
            message=f"Exit node {node.stage_id} cannot be AGENT (must be DETERMINISTIC)",
            source=EngineErrorSource.RUNTIME,
            severity=Severity.ERROR,
            stage_id=node.stage_id
        )

    # Task status must be set
    if task.status == UniversalStatus.PENDING:
        raise EngineError(
            error_id="exit_status_not_set",
            code=EngineErrorCode.INVALID_STATE,
            message=f"Exit node {node.stage_id}: task.status not set (still PENDING)",
            source=EngineErrorSource.RUNTIME,
            severity=Severity.ERROR,
            stage_id=node.stage_id
        )
```

---

### Step 5: Implement `always_fail` Override in Exit Nodes

**File**: `src/agent_engine/runtime/router.py`

**Update EXIT node handling** to apply `always_fail` override:

```python
def _execute_work_item(self, work_item: WorkItem) -> None:
    """..."""

    # ... execute node via node_executor ...

    # Handle EXIT nodes
    if node.role == NodeRole.EXIT:
        # Apply always_fail override if specified
        if node.always_fail:
            task.status = UniversalStatus.FAILED
            self.task_manager.update_task_status(task.task_id, UniversalStatus.FAILED)

        # Mark task as concluded
        task.lifecycle = TaskLifecycle.CONCLUDED
        self.task_manager.update_task_lifecycle(task.task_id, TaskLifecycle.CONCLUDED)

        return task  # Execution complete
```

**Why**: Per SPEC §7.3, exit nodes marked `always_fail` override any existing success to failure.

---

### Step 6: Implement `continue_on_failure` Logic

**File**: `src/agent_engine/runtime/router.py`

**Update error handling** in `_execute_work_item`:

```python
def _execute_work_item(self, work_item: WorkItem) -> None:
    """Execute a single work item (task at a node).

    Handles node execution, error recovery, and routing.
    """
    task = self.task_manager.get_task(work_item.task_id)
    node = self.dag.nodes[work_item.node_id]

    # Execute node
    record, output = self.node_executor.execute_node(task, node)

    # Update task history
    task.history.append(record)
    self.task_manager.record_stage_result(task.task_id, record)

    # Check if node failed
    node_failed = (record.node_status == UniversalStatus.FAILED)

    if node_failed:
        # Node failed - check continue_on_failure
        if node.continue_on_failure:
            # Continue execution despite failure
            # Task status may become PARTIAL if this was critical
            # For now, just continue to next node
            pass
        else:
            # Halt execution - fail the task
            task.status = UniversalStatus.FAILED
            task.lifecycle = TaskLifecycle.CONCLUDED
            self.task_manager.update_task_status(task.task_id, UniversalStatus.FAILED)
            self.task_manager.update_task_lifecycle(task.task_id, TaskLifecycle.CONCLUDED)
            return  # Stop execution

    # Update task current output
    if output is not None:
        task.current_output = output
        self.task_manager.update_task_output(task.task_id, output)

    # Route to next node
    # ... existing routing logic ...
```

**Why**: Per SPEC §3.5, nodes may specify `continue_on_failure` to continue execution despite failure.

---

### Step 7: Implement Task Status Propagation

**File**: `src/agent_engine/runtime/task_manager.py`

**Add methods** for task status management:

```python
def update_task_status(self, task_id: str, status: UniversalStatus) -> None:
    """Update task status.

    Args:
        task_id: Task to update
        status: New status value
    """
    task = self.tasks.get(task_id)
    if task:
        task.status = status

def update_task_lifecycle(self, task_id: str, lifecycle: TaskLifecycle) -> None:
    """Update task lifecycle.

    Args:
        task_id: Task to update
        lifecycle: New lifecycle value
    """
    task = self.tasks.get(task_id)
    if task:
        task.lifecycle = lifecycle

def update_task_output(self, task_id: str, output: Any) -> None:
    """Update task current output.

    Args:
        task_id: Task to update
        output: New output value
    """
    task = self.tasks.get(task_id)
    if task:
        task.current_output = output
```

**Why**: Centralize task state updates for observability and consistency.

---

### Step 8: Implement Merge Node Failure Handling

**File**: `src/agent_engine/schemas/stage.py`

**Add merge failure configuration** to Node schema:

```python
merge_failure_mode: Optional[str] = Field(
    default="fail_on_any",
    description="How merge handles failures: 'fail_on_any', 'ignore_failures', 'partial'"
)
```

**Possible values**:
- `"fail_on_any"` (default): Merge fails if any input failed
- `"ignore_failures"`: Only process successful inputs, ignore failures
- `"partial"`: Produce PARTIAL status if some inputs failed

**File**: `src/agent_engine/runtime/router.py`

**Update merge handling** in `_route_merge`:

```python
def _route_merge(self, task: Task, node: Node) -> Optional[str]:
    """Handle MERGE node routing with failure handling.

    Per AGENT_ENGINE_SPEC §3.4:
    - Merge nodes may ignore or consider failure metadata based on configuration
    - Merge may produce PARTIAL status when mixing success/failure
    """
    # ... existing merge logic to collect inputs ...

    # Check for failures in upstream tasks
    failed_inputs = [inp for inp in merge_inputs if inp.status == UniversalStatus.FAILED]
    successful_inputs = [inp for inp in merge_inputs if inp.status == UniversalStatus.COMPLETED]

    # Apply merge failure mode
    failure_mode = node.merge_failure_mode or "fail_on_any"

    if failure_mode == "fail_on_any":
        if failed_inputs:
            # Fail the merge task
            task.status = UniversalStatus.FAILED
            self.task_manager.update_task_status(task.task_id, UniversalStatus.FAILED)
            # Continue to exit (will be handled by router)

    elif failure_mode == "ignore_failures":
        # Only pass successful inputs to merge node
        merge_inputs = successful_inputs
        # Task status remains based on merge output

    elif failure_mode == "partial":
        if failed_inputs and successful_inputs:
            # Mixed success/failure → PARTIAL
            task.status = UniversalStatus.PARTIAL
            self.task_manager.update_task_status(task.task_id, UniversalStatus.PARTIAL)
        elif failed_inputs:
            # All failed → FAILED
            task.status = UniversalStatus.FAILED
            self.task_manager.update_task_status(task.task_id, UniversalStatus.FAILED)
        # else: all successful → keep status as is

    # ... rest of merge routing ...
```

**Why**: Per SPEC §3.4, merge nodes may ignore or consider failure metadata based on configuration.

---

### Step 9: Implement Subtask/Clone Partial Status Propagation

**File**: `src/agent_engine/runtime/task_manager.py`

**Update completion checks** to set PARTIAL status:

```python
def check_clone_completion(self, parent_task_id: str) -> bool:
    """Check if any clone of parent has completed successfully.

    Per AGENT_ENGINE_SPEC §2.1:
    - Parent completes when ONE clone succeeds (unless merged)
    - If some clones fail but one succeeds → parent COMPLETED
    - If all clones fail → parent FAILED

    Returns:
        True if at least one clone completed successfully
    """
    parent = self.tasks.get(parent_task_id)
    if not parent or not parent.child_task_ids:
        return False

    completed_clones = []
    failed_clones = []

    for child_id in parent.child_task_ids:
        child = self.tasks.get(child_id)
        if child and child.lineage and child.lineage.lineage_type == "clone":
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

def check_subtask_completion(self, parent_task_id: str) -> bool:
    """Check if all subtasks of parent have completed.

    Per AGENT_ENGINE_SPEC §2.1:
    - Parent completes when ALL subtasks succeed (unless merged)
    - If some subtasks fail → parent PARTIAL (if merge allows)
    - If all subtasks fail → parent FAILED

    Returns:
        True if all subtasks have reached terminal state
    """
    parent = self.tasks.get(parent_task_id)
    if not parent or not parent.child_task_ids:
        return False

    completed_subtasks = []
    failed_subtasks = []

    for child_id in parent.child_task_ids:
        child = self.tasks.get(child_id)
        if child and child.lineage and child.lineage.lineage_type == "subtask":
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
```

**Why**: Per SPEC §7.2, task enters `partial` when some subtasks/clones fail but parent allows partial completion.

---

### Step 10: Add Exit Node Status Validation

**File**: `src/agent_engine/runtime/router.py`

**Add pre-exit status check** before executing exit node:

```python
def _execute_work_item(self, work_item: WorkItem) -> None:
    """..."""

    # Before executing exit node, validate status is set
    if node.role == NodeRole.EXIT:
        if task.status == UniversalStatus.PENDING:
            # Task status not set - this is an error
            error = EngineError(
                error_id="exit_status_not_set",
                code=EngineErrorCode.INVALID_STATE,
                message=f"Task {task.task_id} reached exit node {node.stage_id} with status=PENDING",
                source=EngineErrorSource.RUNTIME,
                severity=Severity.ERROR,
                stage_id=node.stage_id
            )
            # Set task to FAILED and conclude
            task.status = UniversalStatus.FAILED
            task.lifecycle = TaskLifecycle.CONCLUDED
            self.task_manager.update_task_status(task.task_id, UniversalStatus.FAILED)
            return

    # ... rest of execution ...
```

**Why**: Per SPEC §3.4, task status must be set *before* reaching an exit node.

---

### Step 11: Update Tests

**Create**: `tests/test_phase7_error_handling.py`

**Test Coverage** (minimum 25 tests):

1. **PARTIAL Status** (3 tests):
   - Test PARTIAL status in UniversalStatus enum
   - Test task with PARTIAL status serialization
   - Test PARTIAL status distinct from FAILED/COMPLETED

2. **Exit Node Validation** (6 tests):
   - Test EXIT node must be DETERMINISTIC (rejects AGENT)
   - Test EXIT node cannot have tools
   - Test EXIT node must have ≥1 inbound edge
   - Test EXIT node cannot have outbound edges
   - Test always_fail flag only valid for EXIT nodes
   - Test exit node execution validation

3. **always_fail Behavior** (3 tests):
   - Test exit node with always_fail=True overrides COMPLETED to FAILED
   - Test exit node with always_fail=False preserves status
   - Test always_fail on non-exit node raises error

4. **continue_on_failure Logic** (4 tests):
   - Test node with continue_on_failure=True continues despite failure
   - Test node with continue_on_failure=False halts on failure
   - Test task status after continue_on_failure=True node fails
   - Test execution path after continue_on_failure

5. **Merge Failure Handling** (4 tests):
   - Test merge with merge_failure_mode="fail_on_any" fails when any input fails
   - Test merge with merge_failure_mode="ignore_failures" processes only successes
   - Test merge with merge_failure_mode="partial" produces PARTIAL status
   - Test merge with all failures vs mixed results

6. **Task Status Propagation** (3 tests):
   - Test task status updated via update_task_status
   - Test task lifecycle updated via update_task_lifecycle
   - Test task output updated via update_task_output

7. **Clone/Subtask Partial Status** (2 tests):
   - Test parent PARTIAL when some subtasks fail
   - Test parent COMPLETED when any clone succeeds despite other failures

8. **Pre-Exit Status Validation** (2 tests):
   - Test exit node rejects task with status=PENDING
   - Test exit node accepts task with status set (COMPLETED/FAILED/PARTIAL)

**Update Existing Tests**:
- Update tests that create EXIT nodes to ensure kind=DETERMINISTIC
- Update tests that expect specific error behaviors
- Ensure all Phase 1-6 tests still pass (no regressions)

---

### Step 12: Update Documentation

**File**: `README.md`

**Add Phase 7 section**:

1. Error Handling & Status Propagation overview
2. UniversalStatus values (including PARTIAL)
3. continue_on_failure configuration
4. Exit node requirements and always_fail flag
5. Merge failure modes
6. Task status propagation rules

**File**: `docs/operational/PLAN_BUILD_AGENT_ENGINE.md`

**Update Phase 7 status**:
- Mark as "✅ COMPLETE"
- Add summary of changes
- Add acceptance criteria checklist

---

## SECTION 4 — Acceptance Criteria

Phase 7 is complete when ALL of the following are verified:

### 4.1 Status Model

- [ ] PARTIAL status added to UniversalStatus enum
- [ ] PARTIAL status distinct from FAILED (some work succeeded)
- [ ] PARTIAL status used for mixed subtask/clone results
- [ ] Documentation updated to describe PARTIAL semantics

### 4.2 Exit Node Validation

- [ ] Exit nodes validated at DAG load time (not runtime)
- [ ] Exit node must have kind=DETERMINISTIC (rejects AGENT)
- [ ] Exit node cannot specify tools
- [ ] Exit node must have ≥1 inbound edges
- [ ] Exit node cannot have outbound edges
- [ ] always_fail flag only valid for EXIT nodes
- [ ] Validation errors clear and actionable

### 4.3 Exit Node Behavior

- [ ] Exit nodes are read-only (do not modify task.current_output)
- [ ] Exit nodes cannot invoke agents
- [ ] Exit nodes cannot call tools
- [ ] Exit node default implementation is identity transform
- [ ] always_fail=True overrides task status to FAILED
- [ ] always_fail=False preserves existing status

### 4.4 Pre-Exit Status Validation

- [ ] Router validates task status is set before executing exit node
- [ ] Task with status=PENDING at exit raises error or auto-fails
- [ ] Task with status=COMPLETED/FAILED/PARTIAL accepted at exit
- [ ] Error message clear when status not set

### 4.5 continue_on_failure Logic

- [ ] Node with continue_on_failure=True continues execution on failure
- [ ] Node with continue_on_failure=False halts execution on failure
- [ ] Task history records node failure even with continue_on_failure=True
- [ ] Task status may become PARTIAL when continuing after failure

### 4.6 Merge Failure Handling

- [ ] Merge node with merge_failure_mode="fail_on_any" fails if any input fails
- [ ] Merge node with merge_failure_mode="ignore_failures" processes only successes
- [ ] Merge node with merge_failure_mode="partial" produces PARTIAL on mixed results
- [ ] Default merge_failure_mode is "fail_on_any"

### 4.7 Task Status Propagation

- [ ] Task status updated correctly via TaskManager methods
- [ ] Task lifecycle updated correctly via TaskManager methods
- [ ] Task output updated correctly via TaskManager methods
- [ ] Status propagation from tools → nodes → tasks works correctly

### 4.8 Clone/Subtask Partial Status

- [ ] Parent task COMPLETED when any clone succeeds (others may fail)
- [ ] Parent task FAILED when all clones fail
- [ ] Parent task PARTIAL when some subtasks fail but not all
- [ ] Parent task COMPLETED when all subtasks succeed
- [ ] Parent task FAILED when all subtasks fail

### 4.9 Test Coverage

- [ ] At least 25 new Phase 7 tests added
- [ ] All error handling scenarios covered
- [ ] All exit node constraints tested
- [ ] All status propagation paths tested
- [ ] All tests passing (610 existing + 25 new = 635 minimum)

### 4.10 Documentation

- [ ] README.md updated with Phase 7 section
- [ ] Error handling semantics documented
- [ ] Status propagation rules documented
- [ ] Exit node requirements documented
- [ ] Example configurations provided

### 4.11 No Regressions

- [ ] All Phase 1-6 tests still passing
- [ ] No breaking changes to existing APIs
- [ ] Backward compatible with existing error handling

---

## SECTION 5 — Clarifying Questions

**None.**

All required information is present in canonical specifications and existing code analysis. Phase 7 can be implemented deterministically following this plan.
