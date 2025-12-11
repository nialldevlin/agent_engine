# Multi-Task Isolation Guarantees

**Phase 17: Multi-Task Query Methods**

## Overview

The Agent Engine provides multi-task execution and query capabilities while maintaining task isolation guarantees. Each task executes independently with separate memory and state management.

## Task Isolation Model

### Memory Isolation

Each task has independent memory scopes:

- **Task Memory** (`task_memory:{task_id}`): Local scope for a single task's execution
- **Project Memory** (`project_memory:{project_id}`): Shared scope for tasks in the same project
- **Global Memory** (`global_memory:default`): Shared scope across all tasks

Memory stores are designed to prevent cross-contamination:

```python
# Each task gets its own memory reference
task.task_memory_ref = f"task_memory:{task_id}"
task.project_memory_ref = f"project_memory:{project_id}"
task.global_memory_ref = "global_memory:default"
```

### Execution Isolation

Tasks execute sequentially (Phase 17) with no concurrent execution:

```python
# Sequential execution guarantees
results = engine.run_multiple([input1, input2, input3])
# Each input completes fully before the next begins
```

Benefits of sequential execution:
- No race conditions on shared resources
- Predictable execution order
- Clear error attribution
- Simplified debugging

### State Isolation

Task state is maintained independently:

```python
# Each task has separate state tracking
task.stage_results: Dict[str, StageExecutionRecord]  # Per-task execution results
task.routing_trace: List[RoutingDecision]            # Per-task routing decisions
task.current_output: Any                             # Per-task output
```

## Task Querying

The Inspector API provides read-only access without affecting task state:

```python
inspector = engine.create_inspector()

# Query methods never modify task state
task = inspector.get_task(task_id)
history = inspector.get_task_history(task_id)
artifacts = inspector.get_task_artifacts(task_id)
events = inspector.get_task_events(task_id)
summary = inspector.get_task_summary(task_id)
```

## Multi-Task Batch Operations

### Sequential Execution

```python
# Execute multiple inputs sequentially
results = engine.run_multiple([input1, input2, input3])

# Each task:
# 1. Executes from start to exit
# 2. Generates unique task_id
# 3. Maintains isolated memory
# 4. Produces separate result
```

### Task Management

```python
# Get all tracked tasks
all_tasks = engine.get_all_task_ids()

# Query by status
pending = task_manager.get_tasks_by_status(UniversalStatus.PENDING)
completed = task_manager.get_tasks_by_status(UniversalStatus.COMPLETED)

# Count tasks
count = task_manager.get_task_count()

# Clean up completed tasks from memory
removed = task_manager.clear_completed_tasks()
```

## Isolation Guarantees

The following guarantees are provided:

### 1. Task ID Uniqueness

```
Convention: task-{spec_id}-{uuid_suffix}

Each task receives a unique ID generated from:
- Task spec ID
- Random UUID suffix

Guarantees: No two tasks have the same ID
```

### 2. Memory Reference Isolation

```
task_memory_ref = f"task_memory:{task_id}"
project_memory_ref = f"project_memory:{project_id}"
global_memory_ref = "global_memory:default"

Guarantees:
- Task-level memory is per-task only
- Project memory is shared only within project
- Global memory is shared across all tasks
```

### 3. Execution Order Guarantee (Sequential)

```
run_multiple([task1, task2, task3]) guarantees:
1. task1 executes and completes
2. task2 starts after task1 completes
3. task3 starts after task2 completes

Guarantees: No concurrent execution, predictable order
```

### 4. Error Isolation

```
If task N fails:
- Task N status = FAILED
- Task N+1 still executes (not cancelled)
- Task N errors isolated to task N's records

Guarantees: One task failure doesn't affect others
```

### 5. State Immutability After Query

```
inspector.get_task(task_id)
inspector.get_task_history(task_id)
inspector.get_task_artifacts(task_id)
inspector.get_task_events(task_id)
inspector.get_task_summary(task_id)

Guarantees: Read-only queries never modify task state
```

## Checkpoint Isolation

Tasks can be persisted to disk independently:

```python
task_manager.save_checkpoint(task_id)
# Creates: .agent_engine/tasks/{project_id}/{task_id}.json

task_manager.load_checkpoint(task_id)
# Loads from checkpoint without affecting other tasks
```

Isolation:
- Each checkpoint is independent
- Checkpoint restore doesn't affect other tasks
- Checkpoints use project-based directory structure

## Child Task Isolation

### Clone Tasks (Branch Node)

```python
parent_task = task_manager.create_task(spec)
clone_task = task_manager.create_clone(parent_task, "branch_label")

Isolation:
- clone_task.parent_task_id = parent_task.task_id
- clone_task.task_id is unique
- clone_task.task_memory_ref is unique
- Clones inherit parent's project/global memory references
```

### Subtask Isolation (Split Node)

```python
parent_task = task_manager.create_task(spec)
subtask = task_manager.create_subtask(parent_task, subtask_input)

Isolation:
- subtask.parent_task_id = parent_task.task_id
- subtask.task_id is unique
- subtask.spec is distinct (own input)
- subtask.task_memory_ref is unique
- Subtasks inherit parent's project/global memory references
```

## Implications for Multi-Task Workflows

### Safe for Parallel Submission (Future)

While Phase 17 implements sequential execution, the isolation model is designed for future concurrent execution:

- Each task can run on separate threads/processes
- Memory isolation prevents race conditions
- Task ID uniqueness prevents collisions
- Checkpoint mechanism enables resumption

### Safe for Long-Running Workflows

Multiple tasks can be queued and executed over time:

```python
# Day 1: Queue 100 tasks
for i in range(100):
    engine.run(input_i)

# Day 2: Query existing tasks
all_ids = engine.get_all_task_ids()
summary = engine.get_task_summary(all_ids[0])

# Day 3: Continue with more tasks
engine.run(new_input)
```

Each task maintains independence across time.

## Example: Isolated Multi-Task Execution

```python
# Initialize engine
engine = Engine.from_config_dir("./config")

# Execute 3 tasks sequentially
inputs = [
    {"query": "What is Python?"},
    {"query": "What is TypeScript?"},
    {"query": "What is Rust?"}
]

results = engine.run_multiple(inputs)

# Each result has isolated state
for i, result in enumerate(results):
    print(f"Task {i}: {result['task_id']} - {result['status']}")
    # Task 0: task-query-abc123 - completed
    # Task 1: task-query-def456 - completed
    # Task 2: task-query-ghi789 - completed

# Query all tasks without modification
inspector = engine.create_inspector()
for task_id in engine.get_all_task_ids():
    summary = inspector.get_task_summary(task_id)
    print(f"{task_id}: {summary['status']}")
```

## Future Enhancements

Future phases may add:

1. **Concurrent Execution**: Parallel task execution (Phase 18+)
   - Requires task-safe memory store implementations
   - Current isolation model supports this

2. **Task Cancellation**: Stop running tasks (Phase 18+)
   - Isolated state allows clean cancellation
   - No impact on other tasks

3. **Task Dependencies**: Define task ordering (Phase 18+)
   - Can chain tasks based on results
   - Memory references enable data passing

4. **Task Groups**: Batch operations on task sets (Phase 18+)
   - Query operations on multiple tasks
   - Bulk status updates

## Conclusion

The Agent Engine multi-task model provides strong isolation guarantees:

- **Each task is independent**: Separate ID, memory refs, and state
- **Sequential execution**: No concurrency complexity (Phase 17)
- **Memory scoping**: Three-tier isolation (task, project, global)
- **Read-only queries**: No side effects from inspection
- **Error containment**: Task failures don't cascade

These guarantees enable safe, predictable multi-task workflows while maintaining the foundation for future concurrent execution.
