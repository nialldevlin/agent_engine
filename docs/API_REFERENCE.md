# Agent Engine API Reference

Complete documentation of the public API for Agent Engine.

## Table of Contents

1. [Engine Class](#engine-class)
2. [REPL & CLI](#repl--cli)
3. [Task & Execution](#task--execution)
4. [Event & Telemetry](#event--telemetry)
5. [Memory Stores](#memory-stores)
6. [Schemas & Validation](#schemas--validation)
7. [Exceptions](#exceptions)

---

## Engine Class

The main entry point for Agent Engine.

### `Engine.from_config_dir(config_dir: str) -> Engine`

Initialize an engine from a configuration directory.

**Parameters:**
- `config_dir` (str): Path to directory containing YAML manifests

**Returns:**
- `Engine`: Fully initialized engine instance

**Required Files:**
- `workflow.yaml` - DAG definition
- `agents.yaml` - Agent configurations
- `tools.yaml` - Tool definitions

**Optional Files:**
- `memory.yaml` - Memory stores and context profiles
- `plugins.yaml` - Plugin configurations
- `cli_profiles.yaml` - CLI behavior

**Example:**
```python
from agent_engine import Engine

engine = Engine.from_config_dir("./config")
```

**Raises:**
- `ManifestLoadError` - If required manifest missing or invalid YAML
- `SchemaValidationError` - If manifest violates schema
- `DAGValidationError` - If DAG structure invalid

---

### `Engine.run(input_data: dict) -> dict`

Execute the workflow with given input.

**Parameters:**
- `input_data` (dict): Input payload (validated against start node schema)

**Returns:**
- dict with keys:
  - `task_id` (str): Unique task identifier
  - `status` (str): "success", "failure", or "partial"
  - `output` (any): Final output from EXIT node
  - `start_node` (str): Starting node ID
  - `current_node` (str): Current/final node ID
  - `execution_time_ms` (float): Total execution time
  - `node_sequence` (list[str]): All executed nodes in order

**Example:**
```python
result = engine.run({
    "request": "analyze data",
    "file": "/path/to/file.txt"
})

print(f"Task {result['task_id']}: {result['status']}")
print(f"Output: {result['output']}")
```

**Raises:**
- `SchemaValidationError` - If input doesn't match start node schema
- `RuntimeError` - If DAG is invalid or execution fails
- `KeyboardInterrupt` - If interrupted during execution

---

### `Engine.run_multiple(inputs: list[dict]) -> list[dict]`

Execute multiple tasks sequentially with full isolation guarantees.

**Parameters:**
- `inputs` (list[dict]): List of input payloads validated against the start node schema

**Returns:**
- list of result dicts (same shape as `Engine.run`), one per input, executed in order

**Behavior:**
- Tasks never run concurrently; each task gets unique `task_id` and isolated memory (`task/project/global` scopes)
- Failures in one task do not block subsequent tasks

**Isolation:** Tasks run sequentially with isolated task/project/global memory; failures in one task do not affect others.

---

### `Engine.create_repl() -> REPL`

Create an interactive REPL for multi-turn sessions.

**Returns:**
- `REPL`: REPL instance ready to run

**Example:**
```python
engine = Engine.from_config_dir("./config")
repl = engine.create_repl()
repl.run()
```

---

### `Engine.get_events(task_id: str = None) -> list[Event]`

Get all events emitted during execution.

**Parameters:**
- `task_id` (str, optional): Filter by task ID; if None, returns all

**Returns:**
- list of `Event` objects

**Example:**
```python
result = engine.run({"request": "test"})
task_events = engine.get_events(result["task_id"])
for event in task_events:
    print(f"{event.type}: {event.payload}")
```

---

### `Engine.get_events_by_type(event_type: str) -> list[Event]`

Get events filtered by type.

**Parameters:**
- `event_type` (str): Event type (e.g., "task_started", "node_completed")

**Returns:**
- list of matching `Event` objects

**Supported Types:**
- `task_started`, `task_completed`, `task_failed`
- `node_started`, `node_completed`, `node_failed`
- `tool_invoked`, `tool_completed`, `tool_failed`
- `context_assembled`, `context_failed`
- `routing_decision`, `routing_branch`, `routing_split`, `routing_merge`
- `clone_created`, `subtask_created`

---

### `Engine.get_events_by_task(task_id: str) -> list[Event]`

Get events for a specific task.

**Parameters:**
- `task_id` (str): Task identifier

**Returns:**
- list of events for that task

---

### `Engine.clear_events()`

Clear all accumulated events.

**Example:**
```python
engine.clear_events()
result = engine.run({"request": "test"})
# Only new events are present
```

---

### `Engine.get_plugin_registry() -> PluginRegistry`

Access the plugin registry.

**Returns:**
- `PluginRegistry`: Plugin management interface

**Example:**
```python
registry = engine.get_plugin_registry()
plugins = registry.list_plugins()
```

---

### `Engine.get_memory_store(store_id: str) -> MemoryStore`

Get a memory store by ID.

**Parameters:**
- `store_id` (str): "task", "project", or "global"

**Returns:**
- `MemoryStore`: The requested memory store

**Example:**
```python
task_store = engine.get_memory_store("task")
task_store.add("key", {"data": "value"})
```

---

## Inspector & Task Queries

Inspector APIs provide read-only access to task state without mutating execution.

### `Engine.create_inspector() -> Inspector`

Returns an Inspector instance bound to the engine.

### `Inspector.get_task(task_id: str) -> Task`
### `Inspector.get_task_history(task_id: str) -> list`
### `Inspector.get_task_artifacts(task_id: str) -> list`
### `Inspector.get_task_events(task_id: str) -> list`
### `Inspector.get_task_summary(task_id: str) -> dict`

All inspector methods are read-only and preserve task state.

---

## Task Manager Helpers

### `Engine.get_all_task_ids() -> list[str]`
### `Engine.get_tasks_by_status(status: str) -> list[Task]`
### `Engine.get_task_count() -> int`
### `Engine.clear_completed_tasks() -> int`

These helpers allow querying tracked tasks (pending/running/completed) without mutating in-flight executions.

## REPL & CLI

### `REPL` Class

Interactive Read-Eval-Print Loop for multi-turn sessions.

#### `REPL.run()`

Start the interactive REPL.

**Example:**
```python
engine = Engine.from_config_dir("./config")
repl = engine.create_repl()
repl.run()
```

Enters interactive loop with prompt showing current profile.

---

### Built-in Commands

All REPLs support these commands:

#### `/help [command]`

Show help for all commands or specific command.

```
[default]> /help
[default]> /help attach
```

#### `/mode [profile_id]`

Show current profile or switch profiles.

```
[default]> /mode
Current: default

[default]> /mode production
Switched to profile: production
```

#### `/attach <path>`

Attach a file to session context.

```
[default]> /attach /path/to/file.txt
File attached: /path/to/file.txt
```

#### `/history`

View session history.

```
[default]> /history
1. /attach file.txt
2. hello world
3. /open file.txt
```

#### `/retry`

Re-run the last input.

```
[default]> /retry
Re-running: hello world
...
```

#### `/edit-last`

Edit and re-run last prompt.

```
[default]> /edit-last
hello world
> hello universe (modified)
```

#### `/open <path>`

View file contents.

```
[default]> /open file.txt
<file contents>
```

#### `/diff <path>`

Compare file with generated artifact.

```
[default]> /diff file.txt
<diff output>
```

#### `/apply_patch <path>`

Apply patch to file.

```
[default]> /apply_patch file.txt
Patch applied successfully
```

#### `/quit` or `/exit`

Exit the REPL.

```
[default]> /quit
Goodbye!
```

---

### CliContext

Context passed to command functions.

#### `CliContext.run_engine(input_data: dict) -> dict`

Execute engine with input and record in session.

**Parameters:**
- `input_data` (dict): Input to engine

**Returns:**
- Engine result dict

**Example:**
```python
def my_command(ctx: CliContext, args: str) -> None:
    result = ctx.run_engine({"request": args})
    print(result["output"])
```

#### `CliContext.attach_file(path: str)`

Attach file to session.

#### `CliContext.get_telemetry() -> list[Event]`

Get recent telemetry events.

#### `CliContext.get_current_profile() -> Profile`

Get active profile.

#### `CliContext.switch_profile(profile_id: str)`

Switch to different profile.

---

### Custom Commands

Register custom commands via decorator:

```python
from agent_engine.cli import register_command, CliContext

@register_command(name="process", aliases=["p"])
def process_command(ctx: CliContext, args: str) -> None:
    """Process command description."""
    result = ctx.run_engine({"action": "process", "data": args})
    print(f"Result: {result}")
```

Or define in config:

```yaml
profiles:
  - id: default
    custom_commands:
      - name: process
        entrypoint: my_app.commands:process_command
        description: Process data
        aliases: [p]
```

---

## Task & Execution

### Task Model

A Task represents one execution of a workflow.

**Fields:**
```python
{
    "task_id": "task-abc123",
    "input": {...},
    "output": {...},
    "status": "success",  # "success", "failure", "partial"
    "start_node": "start",
    "current_node": "exit",
    "execution_time_ms": 1234.5,
    "node_sequence": ["start", "process", "exit"],
    "error": None,
    "lineage": {
        "parent_id": None,
        "type": None,  # "branch-clone", "split-subtask"
        "node_id": None,
        "position": 0
    }
}
```

---

### Runtime Overrides

For runtime control of models, hyperparameters, tool availability, node timeouts, and per-task settings, use the dynamic-parameter APIs described in `docs/DYNAMIC_PARAMETERS.md` (`set_agent_model`, `set_agent_hyperparameters`, `enable_tool`, `set_node_timeout`, `set_task_parameters`, `clear_overrides`). These overrides respect scope precedence (task > project > global > manifest).

---

### Node Roles

Seven semantic node types determine routing behavior:

#### START
- Initializes task
- Always succeeds
- Routes to first connected node
- Only one per workflow

#### LINEAR
- Sequential processing
- Deterministic or agent-driven
- Single input → single output
- Can use tools and context

#### DECISION
- Conditional routing
- Examines node output
- Routes by matching edge labels
- Exactly one outgoing path selected

#### BRANCH
- Creates independent clones
- Parent completes when first clone succeeds
- Each clone executes full downstream DAG
- Clone lineage tracked

#### SPLIT
- Creates parallel subtasks
- Parent waits for all subtasks
- All subtasks execute in parallel
- Results aggregated at MERGE

#### MERGE
- Recombines multiple paths
- Aggregates results from clones/subtasks
- Single output node
- Multiple input paths

#### EXIT
- Terminates workflow
- Returns final output
- Marks task complete
- Only one per workflow

---

## Event & Telemetry

### Event Class

Represents a single operation event.

**Fields:**
```python
{
    "event_id": "evt-abc123",
    "type": "node_completed",  # See EventType enum
    "timestamp": "2024-01-01T12:00:00Z",
    "task_id": "task-abc123",
    "stage_id": "process",  # Node ID
    "payload": {...}  # Event-specific data
}
```

---

### Event Types

#### Task Events

**task_started**
```python
{
    "task_id": "task-abc",
    "spec": {...},
    "mode": "run"
}
```

**task_completed**
```python
{
    "task_id": "task-abc",
    "status": "success",
    "output": {...},
    "execution_time_ms": 1000.0
}
```

**task_failed**
```python
{
    "task_id": "task-abc",
    "error": "Division by zero",
    "node_id": "process"
}
```

#### Node Events

**node_started**
```python
{
    "task_id": "task-abc",
    "node_id": "process",
    "role": "linear",
    "kind": "agent",
    "input": {...}
}
```

**node_completed**
```python
{
    "task_id": "task-abc",
    "node_id": "process",
    "output": {...},
    "execution_time_ms": 500.0
}
```

#### Tool Events

**tool_invoked**
```python
{
    "task_id": "task-abc",
    "node_id": "process",
    "tool_id": "read_file",
    "inputs": {"path": "/file.txt"}
}
```

**tool_completed**
```python
{
    "task_id": "task-abc",
    "node_id": "process",
    "tool_id": "read_file",
    "output": "file contents"
}
```

#### Routing Events

**routing_decision**
```python
{
    "task_id": "task-abc",
    "node_id": "decision",
    "decision": "approved",
    "next_node_id": "process_a"
}
```

**routing_branch**
```python
{
    "task_id": "task-abc",
    "node_id": "branch",
    "clone_count": 3,
    "clone_ids": ["clone-1", "clone-2", "clone-3"]
}
```

---

### Plugin System

Extend behavior with read-only plugins.

```python
from agent_engine.schemas import PluginBase, Event

class MyPlugin(PluginBase):
    def __init__(self, plugin_id: str, config: dict = None):
        super().__init__(plugin_id, config)

    def on_startup(self) -> None:
        """Called when plugin registered."""
        pass

    def on_event(self, event: Event) -> None:
        """Handle event (read-only)."""
        if event.type == "task_completed":
            print(f"Task {event.task_id} completed")

    def on_shutdown(self) -> None:
        """Called when plugin unregistered."""
        pass
```

Register in `plugins.yaml`:

```yaml
plugins:
  - id: my_plugin
    module: my_app.MyPlugin
    enabled: true
    config:
      option1: value1
```

---

### PluginRegistry

Manage plugins.

#### `register(plugin: PluginBase)`

Register a plugin.

```python
registry = engine.get_plugin_registry()
registry.register(MyPlugin("my_id"))
```

#### `unregister(plugin_id: str)`

Unregister a plugin.

```python
registry.unregister("my_id")
```

#### `get_plugin(plugin_id: str) -> PluginBase`

Get a plugin by ID.

```python
plugin = registry.get_plugin("my_id")
```

#### `list_plugins() -> list[str]`

List all registered plugin IDs.

```python
plugin_ids = registry.list_plugins()
```

---

## Memory Stores

### Memory Store Interface

Three memory stores provide persistent context.

#### `MemoryStore.add(key: str, value: any, tags: list[str] = None)`

Store a value.

```python
store = engine.get_memory_store("task")
store.add("document", {"title": "My Doc", "content": "..."})
```

#### `MemoryStore.get(key: str) -> any`

Retrieve a value.

```python
doc = store.get("document")
```

#### `MemoryStore.list(tag: str = None) -> list[tuple[str, any]]`

List all entries, optionally filtered by tag.

```python
entries = store.list(tag="important")
```

#### `MemoryStore.delete(key: str)`

Delete a value.

```python
store.delete("document")
```

#### `MemoryStore.clear()`

Clear all entries.

```python
store.clear()
```

---

### Store Types

#### Task Store
Isolated per-task memory. Cleared between tasks.

```python
task_store = engine.get_memory_store("task")
```

#### Project Store
Shared across all tasks in a project session.

```python
project_store = engine.get_memory_store("project")
```

#### Global Store
Shared across all projects and sessions.

```python
global_store = engine.get_memory_store("global")
```

---

### Context Profiles

Configure memory assembly per node.

```yaml
context_profiles:
  - id: "default"
    max_tokens: 4000
    retrieval_policy: "recency"  # or "semantic" or "hybrid"
    sources:
      - store: "task"
        tags: ["recent"]
      - store: "project"
        tags: []
```

Nodes with `context: "default"` receive assembled context.

---

## Schemas & Validation

### Input/Output Schemas

Define validation for node inputs/outputs in manifests.

**workflow.yaml:**
```yaml
nodes:
  - id: "process"
    kind: "agent"
    role: "linear"
    input_schema: "document"
    output_schema: "result"
```

**schemas/document.json:**
```json
{
  "type": "object",
  "properties": {
    "title": {"type": "string"},
    "content": {"type": "string"}
  },
  "required": ["title", "content"]
}
```

### Schema Validation

All inputs/outputs validated automatically.

```python
# If input doesn't match schema, raises SchemaValidationError
result = engine.run({
    "title": "Missing content"  # Error: required field missing
})
```

---

## Exceptions

### ManifestLoadError

Raised when manifest file is missing or has invalid YAML.

```python
try:
    engine = Engine.from_config_dir("./bad_config")
except ManifestLoadError as e:
    print(f"File: {e.file_name}")
    print(f"Error: {e.message}")
```

**Attributes:**
- `file_name` - Name of the manifest file
- `message` - Error description

---

### SchemaValidationError

Raised when data violates schema constraints.

```python
try:
    engine.run({"invalid": "data"})
except SchemaValidationError as e:
    print(f"File: {e.file_name}")
    print(f"Field: {e.field_path}")
    print(f"Error: {e.message}")
```

**Attributes:**
- `file_name` - Manifest being validated
- `field_path` - JSON path to problematic field
- `message` - Validation error message

---

### DAGValidationError

Raised when DAG structure violates invariants.

```python
try:
    engine = Engine.from_config_dir("./cyclic_config")
except DAGValidationError as e:
    print(f"Error: {e.message}")
    if e.node_id:
        print(f"Node: {e.node_id}")
```

**Attributes:**
- `message` - Error description
- `node_id` - Node involved (optional)

---

### CliError

Raised for CLI framework errors.

```python
from agent_engine.cli import CliError

try:
    # CLI operation
except CliError as e:
    print(f"CLI Error: {e}")
```

---

### CommandError

Raised when custom command fails.

```python
from agent_engine.cli import CommandError

@register_command(name="process")
def process_cmd(ctx: CliContext, args: str) -> None:
    if not args:
        raise CommandError("Please provide input")
```

---

## Complete Example

Here's a complete example using the full API:

```python
from agent_engine import Engine
from agent_engine.cli import register_command, CliContext
from agent_engine.schemas import PluginBase, Event

# Define custom plugin
class LogPlugin(PluginBase):
    def on_event(self, event: Event) -> None:
        print(f"[{event.type}] {event.payload}")

# Define custom command
@register_command(name="analyze")
def analyze_cmd(ctx: CliContext, args: str) -> None:
    result = ctx.run_engine({"action": "analyze", "data": args})
    print(f"Analysis complete: {result['output']}")

# Initialize engine
engine = Engine.from_config_dir("./config")

# Register plugin
registry = engine.get_plugin_registry()
registry.register(LogPlugin("logger"))

# Run workflow
result = engine.run({"request": "test"})
print(f"Task {result['task_id']}: {result['status']}")

# Inspect events
events = engine.get_events(result["task_id"])
print(f"Events: {len(events)}")

# Interactive session
repl = engine.create_repl()
repl.run()
```

---

## See Also

- [Architecture](ARCHITECTURE.md)
- [Developer Guide](DEVELOPER_GUIDE.md)
- [CLI Framework](CLI_FRAMEWORK.md)
- [Specification](canonical/AGENT_ENGINE_SPEC.md)
