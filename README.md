# Agent Engine

A configuration-first orchestration framework for executing structured workflows that combine deterministic logic and large-language-model (LLM) agents.

## Overview

Agent Engine executes workflows as directed acyclic graphs (DAGs) specified through declarative manifests. The engine provides routing, validation, task management, parallelism, and observability while projects define workflow logic, schemas, context profiles, and tool choices.

## Installation

```bash
pip install -e .
```

## Quick Start

### 1. Create a Config Directory

Create a directory structure with required manifests:

```
my_project/
├── workflow.yaml
├── agents.yaml
├── tools.yaml
├── memory.yaml (optional)
├── plugins.yaml (optional)
└── schemas/ (optional)
```

### 2. Define Your Workflow (workflow.yaml)

```yaml
nodes:
  - id: "start"
    kind: "deterministic"
    role: "start"
    default_start: true
    context: "none"
    continue_on_failure: false

  - id: "process"
    kind: "agent"
    role: "linear"
    context: "global"
    tools: ["read_file"]
    continue_on_failure: false

  - id: "exit"
    kind: "deterministic"
    role: "exit"
    context: "none"
    continue_on_failure: false

edges:
  - from: "start"
    to: "process"
  - from: "process"
    to: "exit"
```

### 3. Define Agents (agents.yaml)

```yaml
agents:
  - id: "default_agent"
    kind: "agent"
    llm: "anthropic/claude-3-5-sonnet"
    config: {}
```

### 4. Define Tools (tools.yaml)

```yaml
tools:
  - id: "read_file"
    type: "filesystem"
    entrypoint: "agent_engine.tools.filesystem:read_file"
    permissions:
      allow_network: false
      allow_shell: false
      root: false
```

### 5. Initialize and Run Engine

```python
from agent_engine import Engine

# Load engine from config directory
engine = Engine.from_config_dir("my_project")

# Run workflow (Phase 2: returns initialization stub)
result = engine.run({"request": "analyze codebase"})
print(result)
# Output: {"status": "initialized", "dag_valid": True, "start_node": "start", ...}
```

## Engine Initialization

The `Engine.from_config_dir(path)` method follows this sequence (per AGENT_ENGINE_SPEC §8):

1. **Load Manifests** - Parse YAML files (workflow, agents, tools, memory, plugins)
2. **Validate Schemas** - Validate all manifest data against canonical schemas
3. **Construct DAG** - Build in-memory graph with nodes, edges, and adjacency
4. **Validate DAG** - Enforce structural invariants (acyclic, reachable, role constraints)
5. **Initialize Memory** - Create empty store stubs (task, project, global)
6. **Register Adapters** - Register tools and LLM providers
7. **Load Plugins** - Initialize read-only observer plugins
8. **Return Engine** - Fully initialized engine instance

## Required Manifests

### workflow.yaml

Defines the DAG structure with nodes and edges.

**Node Fields:**
- `id` - Unique node identifier
- `kind` - "agent" or "deterministic"
- `role` - "start", "linear", "decision", "branch", "split", "merge", or "exit"
- `default_start` - Boolean (only for start nodes)
- `context` - Context profile ID, "global", or "none"
- `tools` - List of tool IDs (optional)
- `continue_on_failure` - Boolean

**Edge Fields:**
- `from` - Source node ID
- `to` - Target node ID
- `label` - Optional label for decision routing

Example:
```yaml
nodes:
  - id: "start"
    kind: "deterministic"
    role: "start"
    default_start: true
    context: "none"
    continue_on_failure: false
  - id: "main"
    kind: "agent"
    role: "linear"
    context: "global"
    tools: ["read_file"]
    continue_on_failure: false
  - id: "exit"
    kind: "deterministic"
    role: "exit"
    context: "none"
    continue_on_failure: false

edges:
  - from: "start"
    to: "main"
  - from: "main"
    to: "exit"
```

### agents.yaml

Defines LLM agent configurations.

**Agent Fields:**
- `id` - Unique agent identifier
- `kind` - Must be "agent"
- `llm` - LLM provider identifier (e.g., "anthropic/claude-3-5-sonnet")
- `config` - Provider-specific configuration object

Example:
```yaml
agents:
  - id: "default_agent"
    kind: "agent"
    llm: "anthropic/claude-3-5-sonnet"
    config: {}
```

### tools.yaml

Defines deterministic tool configurations.

**Tool Fields:**
- `id` - Unique tool identifier
- `type` - Tool category (e.g., "filesystem", "http", "compute")
- `entrypoint` - Module:function path or command
- `permissions` - Permission object with allow_network, allow_shell, root

Example:
```yaml
tools:
  - id: "read_file"
    type: "filesystem"
    entrypoint: "agent_engine.tools.filesystem:read_file"
    permissions:
      allow_network: false
      allow_shell: false
      root: false
```

## Optional Manifests

### memory.yaml

Defines memory stores and context profiles for managing workflow state and token budgets.

**Memory Stores:**
- `task_store` - Per-task isolated memory
- `project_store` - Project-wide shared memory
- `global_store` - Global shared memory across all projects

**Context Profiles:**
Define how memory is assembled during execution. Each profile specifies token limits, retrieval policies, and source preferences.

Example:
```yaml
memory:
  task_store:
    type: "in_memory"
  project_store:
    type: "in_memory"
  global_store:
    type: "in_memory"
  context_profiles:
    - id: "custom_profile"
      max_tokens: 4000
      retrieval_policy: "recency"  # or "semantic" or "hybrid"
      sources:
        - store: "task"
          tags: []
```

**Default Behavior:**
If memory.yaml is not provided, the engine automatically creates:
- Default in-memory stores for task, project, and global memory
- A `global_default` context profile with standard settings

### plugins.yaml

Defines read-only observer plugins for logging, metrics, and telemetry (Phase 9).

Plugins are loaded during initialization and receive notification events without modifying engine state. Plugins observe all engine events but cannot mutate task state, modify routing, or affect execution flow.

**Plugin Fields:**
- `id` - Unique plugin identifier
- `module` - Python module path to plugin class (e.g., "my_plugins.LoggingPlugin")
- `enabled` - Boolean, whether plugin is loaded (default: true)
- `config` - Optional plugin-specific configuration dict

Example:
```yaml
plugins:
  - id: "logger_plugin"
    module: "my_plugins.LoggingPlugin"
    enabled: true
    config:
      log_level: "INFO"
      log_all_events: true
```

## Error Handling

The engine raises structured exceptions with detailed context:

### ManifestLoadError

Raised when a required manifest is missing or has invalid YAML syntax.

```python
try:
    engine = Engine.from_config_dir("bad_config")
except ManifestLoadError as e:
    print(f"File: {e.file_name}")
    print(f"Error: {e.message}")
```

Attributes:
- `file_name` - Name of the missing/invalid manifest
- `message` - Error description

### SchemaValidationError

Raised when manifest data violates schema constraints (missing required fields, wrong types, invalid values).

```python
try:
    engine = Engine.from_config_dir("invalid_config")
except SchemaValidationError as e:
    print(f"File: {e.file_name}")
    print(f"Field: {e.field_path}")
    print(f"Error: {e.message}")
```

Attributes:
- `file_name` - Name of the invalid manifest
- `field_path` - JSON path to the problematic field
- `message` - Error description

### DAGValidationError

Raised when DAG structure violates canonical invariants (cycles, unreachable nodes, invalid role combinations).

```python
try:
    engine = Engine.from_config_dir("cyclic_config")
except DAGValidationError as e:
    print(f"DAG Error: {e.message}")
    if e.node_id:
        print(f"At node: {e.node_id}")
```

Attributes:
- `message` - Error description
- `node_id` - Node where the error occurred (if applicable)

## Examples

See `examples/minimal_config/` for a complete minimal configuration with all required manifests.

To run the minimal example:

```python
from agent_engine import Engine

engine = Engine.from_config_dir("examples/minimal_config")
result = engine.run({"request": "test"})
print(result)
```

## Telemetry & Event Bus (Phase 8)

The engine provides comprehensive event emission for all major operations, enabling introspection, debugging, and plugin integration.

### Event Types

The engine emits the following event types, each with structured payloads:

#### Task Events
- `task_started` - Emitted when a task begins execution
  - Includes: task_id, spec, mode, timestamp
- `task_completed` - Emitted when a task succeeds
  - Includes: task_id, status, lifecycle, output, timestamp
- `task_failed` - Emitted when a task fails
  - Includes: task_id, error, timestamp

#### Node Events
- `node_started` - Emitted before each node execution
  - Includes: task_id, node_id, role, kind, input, timestamp
- `node_completed` - Emitted after successful node execution
  - Includes: task_id, node_id, output, status, timestamp
- `node_failed` - Emitted after failed node execution
  - Includes: task_id, node_id, error, timestamp

#### Routing Events
- `routing_decision` - Routing decision made at LINEAR or DECISION node
  - Includes: task_id, node_id, decision, next_node_id, timestamp
- `routing_branch` - Clone creation at BRANCH node
  - Includes: task_id, node_id, clone_count, clone_ids, timestamp
- `routing_split` - Subtask creation at SPLIT node
  - Includes: task_id, node_id, subtask_count, subtask_ids, timestamp
- `routing_merge` - Merge operation at MERGE node
  - Includes: task_id, node_id, input_count, input_statuses, timestamp

#### Tool Events
- `tool_invoked` - Before tool execution
  - Includes: task_id, node_id, tool_id, inputs, timestamp
- `tool_completed` - After successful tool execution
  - Includes: task_id, node_id, tool_id, output, status, timestamp
- `tool_failed` - After tool execution failure
  - Includes: task_id, node_id, tool_id, error, timestamp

#### Context Events
- `context_assembled` - After successful context assembly
  - Includes: task_id, node_id, profile_id, item_count, token_count, timestamp
- `context_failed` - On context assembly error
  - Includes: task_id, node_id, error, timestamp

#### Clone/Subtask Events
- `clone_created` - Emitted for each clone created by BRANCH
  - Includes: parent_task_id, clone_id, node_id, lineage, timestamp
- `subtask_created` - Emitted for each subtask created by SPLIT
  - Includes: parent_task_id, subtask_id, node_id, lineage, timestamp

### Accessing Telemetry

The Engine provides methods to access and filter events:

```python
from agent_engine import Engine
from agent_engine.schemas import EventType

engine = Engine.from_config_dir("my_project")
result = engine.run({"request": "analyze codebase"})

# Get all events
all_events = engine.get_events()
print(f"Total events: {len(all_events)}")

# Filter by event type
task_events = engine.get_events_by_type(EventType.TASK)
node_events = engine.get_events_by_type(EventType.STAGE)
routing_events = engine.get_events_by_type(EventType.ROUTING)

# Filter by task
task_id = result["task_id"]
task_events = engine.get_events_by_task(task_id)

# Clear events (if needed)
engine.clear_events()
```

### Event Ordering and Timestamps

- **Ordering**: Events are emitted in execution order and stored in a list
- **Timestamps**: All events have ISO-8601 timestamps in UTC
- **Determinism**: Same execution input produces same event sequence (modulo timestamps)

### Example: Complete Event Trace

```python
engine = Engine.from_config_dir("my_project")
result = engine.run({"request": "analyze codebase"})

# Inspect the complete execution trace
for event in engine.get_events():
    print(f"{event.timestamp} - {event.payload['event']} "
          f"(task: {event.task_id}, node: {event.stage_id})")

# Output:
# 2024-01-15T10:30:45.123Z - task_started (task: task-abc123, node: None)
# 2024-01-15T10:30:45.124Z - node_started (task: task-abc123, node: start)
# 2024-01-15T10:30:45.125Z - context_assembled (task: task-abc123, node: start)
# 2024-01-15T10:30:45.126Z - node_completed (task: task-abc123, node: start)
# 2024-01-15T10:30:45.127Z - routing_decision (task: task-abc123, node: start)
# 2024-01-15T10:30:45.128Z - node_started (task: task-abc123, node: process)
# ...
```

### Implementation Details

- **No Side Effects**: Event emission never affects execution flow
- **Thread-Safe**: Telemetry bus can be accessed safely during execution
- **Serializable**: All event payloads are JSON-serializable for logging/export
- **Optional**: Telemetry can be disabled by passing `telemetry=None` to components

## Plugin System v1 (Phase 9)

The engine provides a read-only plugin system for observing and responding to engine events without modifying execution flow, task state, or routing decisions.

### Creating a Plugin

Plugins inherit from `PluginBase` and implement the `on_event()` method to observe events:

```python
from agent_engine.schemas import PluginBase, Event

class LoggingPlugin(PluginBase):
    """Example plugin that logs all events."""

    def __init__(self, plugin_id: str, config: dict = None):
        super().__init__(plugin_id, config)
        self.event_count = 0

    def on_startup(self) -> None:
        """Called when plugin is registered."""
        print(f"Plugin {self.plugin_id} started")

    def on_event(self, event: Event) -> None:
        """Handle engine event (read-only).

        Important: Plugin must not modify event or access engine internals.
        """
        self.event_count += 1
        print(f"Event {self.event_count}: {event.type.value}")

    def on_shutdown(self) -> None:
        """Called when plugin is unregistered."""
        print(f"Plugin processed {self.event_count} events")
```

### Registering Plugins

Plugins are configured in `plugins.yaml` and automatically loaded during engine initialization:

```yaml
plugins:
  - id: "logging"
    module: "my_app.LoggingPlugin"
    enabled: true
    config:
      log_level: "INFO"
```

The module path must be in format: `package.module.ClassName`

### Plugin Lifecycle

1. **on_startup()** - Called when plugin is registered (optional override)
2. **on_event(event)** - Called for each event emitted by engine (required implementation)
3. **on_shutdown()** - Called when plugin is unregistered (optional override)

### Plugin Isolation Guarantees

Plugins are strictly isolated from engine internals:

- **Read-Only Events**: Events passed to plugins are immutable deep copies
- **Error Isolation**: Plugin exceptions are caught and logged; never affect engine execution
- **No State Mutation**: Plugins cannot mutate task state, DAG structure, or routing decisions
- **Sequential Dispatch**: Plugins are called synchronously after each event; dispatching is deterministic

### Plugin Configuration

Each plugin receives optional configuration from `plugins.yaml`:

```python
class MetricsPlugin(PluginBase):
    def __init__(self, plugin_id: str, config: dict = None):
        super().__init__(plugin_id, config)
        self.sample_rate = self.config.get("sample_rate", 1.0)
        self.buffer_size = self.config.get("buffer_size", 100)
```

### Accessing Plugins from Code

After engine initialization, you can access the plugin registry:

```python
engine = Engine.from_config_dir("config")

# Get plugin registry
registry = engine.get_plugin_registry()

# List all plugins
plugin_ids = registry.list_plugins()

# Get specific plugin
plugin = registry.get_plugin("logging")

# Manually register plugin
from my_app import CustomPlugin
custom = CustomPlugin("custom")
registry.register(custom)

# Unregister plugin
registry.unregister("custom")
```

## Features

### Core Engine
- **DAG-Based Workflows**: Define complex workflows as acyclic directed graphs
- **Seven Node Roles**: START, LINEAR, DECISION, BRANCH, SPLIT, MERGE, EXIT
- **Two Node Kinds**: Deterministic operations and LLM-driven agents
- **Configuration-First**: All behavior defined via YAML manifests (no code)
- **Schema Validation**: All inputs/outputs validated against Pydantic schemas
- **Task Management**: Complete task lifecycle with parent-child lineage tracking

### Execution & Routing
- **Deterministic Routing**: Consistent execution following DAG edges
- **Decision-Based Branching**: Routes based on node output values
- **Clone Management**: BRANCH nodes create independent task clones
- **Subtask Parallelism**: SPLIT nodes create parallel subtasks with merge aggregation
- **Failure Handling**: Per-node continue_on_failure policies with status propagation
- **Context Assembly**: Dynamic memory assembly for each node with token budgets

### Observability & Extensibility
- **Telemetry System**: Complete event emission for all operations
- **Plugin Architecture**: Read-only plugins observe and respond to events
- **Event Logging**: Queryable event history with filtering by type/task
- **Task History**: Full execution trace for each task including all node operations

### CLI & Interaction
- **Interactive REPL**: Multi-turn conversational sessions with profiles
- **Session Management**: History persistence with JSONL format
- **File Operations**: Built-in commands for viewing/editing/diffing files
- **Profile System**: Configure CLI behavior per workflow
- **Command Registry**: Extensible command system with decorator API

### Memory & State
- **Multi-Level Storage**: Task, project, and global memory stores
- **Context Profiles**: Define token budgets and retrieval policies
- **Memory Isolation**: Task-level isolation prevents cross-contamination
- **Semantic Search**: Optional semantic retrieval using embeddings

### Security & Policies
- **Tool Permissions**: Control shell, network, and filesystem access per tool
- **Policy Enforcement**: Declarative security policies for sensitive operations
- **Resource Limits**: Token budgets and task timeouts
- **Input Validation**: All inputs validated before processing

## Implementation Status

| Phase | Feature | Status |
|-------|---------|--------|
| 1 | Canonical Schemas & Manifest Validation | ✅ Complete |
| 2 | Engine Facade & DAG Loader | ✅ Complete |
| 3 | Task Management & Lineage | ✅ Complete |
| 4 | Node Execution & Tool Invocation | ✅ Complete |
| 5 | Router v1.0 (Deterministic DAG Routing) | ✅ Complete |
| 6 | Context Assembly & Memory | ✅ Complete |
| 7 | Node Failure Handling & Lifecycle | ✅ Complete |
| 8 | Telemetry & Event Bus | ✅ Complete |
| 9 | Plugin System v1 (Read-Only Observers) | ✅ Complete |
| 10 | Artifact Storage & Retrieval | ✅ Complete |
| 11 | Metadata & Provenance Tracking | ✅ Complete |
| 12 | Evaluation Framework | ✅ Complete |
| 13 | Performance Metrics & Profiling | ✅ Complete |
| 14 | Security & Policy Layer | ✅ Complete |
| 15 | Adapter Management & Discovery | ✅ Complete |
| 16 | Inspector Mode & Debugging | ✅ Complete |
| 17 | Multi-Task Isolation & Execution | ✅ Complete |
| 18 | CLI Framework (Reusable REPL) | ✅ Complete |
| 19 | (Future) Advanced Routing | ⏳ Planned |
| 20 | (Future) Distributed Execution | ⏳ Planned |
| 21 | (Future) ML Model Management | ⏳ Planned |
| 22 | (Future) Enterprise Features | ⏳ Planned |
| 23 | Example App & Documentation | ✅ Complete |

All 23 phases complete with comprehensive documentation, example apps, and test coverage.

## Documentation

### For Users & Developers

**Getting Started:**
- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** - Complete system architecture with Mermaid diagrams
- **[TUTORIAL.md](docs/TUTORIAL.md)** - Step-by-step walkthrough with mini-editor example
- **[Quick Start](#quick-start)** - 5-minute introduction (above)

**Reference:**
- **[API_REFERENCE.md](docs/API_REFERENCE.md)** - Complete public API documentation
- **[CLI_FRAMEWORK.md](docs/CLI_FRAMEWORK.md)** - Interactive REPL usage guide
- **[DEPLOYMENT.md](docs/DEPLOYMENT.md)** - Production deployment guide
- **[SECURITY.md](docs/SECURITY.md)** - Security best practices
- **[PACKAGING.md](docs/PACKAGING.md)** - PyPI packaging guide

**Examples:**
- **[examples/minimal_config/](examples/minimal_config/)** - Minimal working example
- **[examples/mini_editor/](examples/mini_editor/)** - Mini-editor document creation app

**Canonical Specifications:**
- **[AGENT_ENGINE_SPEC.md](docs/canonical/AGENT_ENGINE_SPEC.md)** - Authoritative technical specification (frozen)
- **[AGENT_ENGINE_OVERVIEW.md](docs/canonical/AGENT_ENGINE_OVERVIEW.md)** - Architectural overview (frozen)
- **[PROJECT_INTEGRATION_SPEC.md](docs/canonical/PROJECT_INTEGRATION_SPEC.md)** - Integration specification (frozen)

**Operational & Development:**
- **[CHANGELOG.md](docs/CHANGELOG.md)** - Release notes and phase completion summaries
- **[PLAN_BUILD_AGENT_ENGINE.md](docs/operational/PLAN_BUILD_AGENT_ENGINE.md)** - v1 roadmap and implementation status
- **[MULTI_TASK_ISOLATION.md](docs/MULTI_TASK_ISOLATION.md)** - Phase 17 multi-task isolation guarantees

## Development

### Running Tests

```bash
pytest tests/
```

### Project Structure

```
agent_engine/
├── src/agent_engine/
│   ├── engine.py              # Main Engine class
│   ├── dag.py                 # DAG data structure
│   ├── manifest_loader.py     # YAML manifest loading
│   ├── schema_validator.py    # Schema validation
│   ├── memory_stores.py       # Memory store implementations
│   ├── adapters.py            # Tool/LLM adapter registry
│   ├── exceptions.py          # Custom exception classes
│   ├── schemas/               # Pydantic schema definitions
│   ├── runtime/               # Runtime execution components
│   ├── tools/                 # Tool implementations
│   ├── patterns/              # Workflow patterns (supervisor, committee)
│   ├── plugins/               # Plugin system
│   └── utils/                 # Utility modules
├── examples/
│   └── minimal_config/        # Minimal working example
├── tests/                     # Test suite
├── docs/                      # Documentation
└── pyproject.toml             # Project configuration
```

### Building and Testing

```bash
# Install dependencies
make install

# Run tests
make test

# Type checking
make typecheck

# Linting and formatting
make lint
make format
```

## CLI Framework v1 (Phase 18)

The Agent Engine includes an interactive REPL (Read-Eval-Print Loop) for multi-turn conversational sessions with workflows.

### Quick Start with REPL

```python
from agent_engine import Engine

# Load engine from config
engine = Engine.from_config_dir("my_project")

# Create and run REPL
repl = engine.create_repl()
repl.run()
```

### Interactive Usage

```
[default]> /help                    # List available commands
[default]> /attach myfile.txt       # Attach file to session
[default]> hello, analyze this      # Send input to engine
[default]> /history                 # View session history
[default]> /mode production         # Switch profiles
[default]> /quit                    # Exit REPL
```

### Profile-Based Configuration

Configure CLI behavior via `cli_profiles.yaml`:

```yaml
profiles:
  - id: default
    session_policies:
      persist_history: true
    input_mappings:
      default:
        attach_files_as_context: true
    telemetry_overlays:
      level: summary
```

### Built-in Commands

The CLI provides 10 built-in commands:

- `/help` - Show command list or help for a command
- `/mode` - Show/switch profiles
- `/attach` - Attach files to session
- `/history` - View session history
- `/retry` - Re-run last input
- `/edit-last` - Edit and re-run last prompt
- `/open` - View file contents
- `/diff` - Compare file with artifact
- `/apply_patch` - Apply patch to file
- `/quit` or `/exit` - Exit REPL

### Custom Commands

Extend the REPL with custom commands:

```python
# my_app/commands.py
from agent_engine.cli import CliContext, CommandError

def my_command(ctx: CliContext, args: str) -> None:
    """Custom command implementation."""
    result = ctx.run_engine(f"process: {args}")
    print(f"Done: {result}")
```

Configure in `cli_profiles.yaml`:

```yaml
profiles:
  - id: default
    custom_commands:
      - name: mycommand
        entrypoint: my_app.commands:my_command
        description: My custom command
        aliases: [mc]
```

### Session Persistence

Sessions automatically persist to JSONL format:

```yaml
session_policies:
  persist_history: true
  history_file: ~/.agent_engine/sessions/history.jsonl
  max_history_items: 1000
```

### Telemetry Integration

The REPL displays telemetry events from workflow execution:

```yaml
telemetry_overlays:
  enabled: true
  level: summary      # "summary" or "verbose"
```

### Learn More

See [docs/CLI_FRAMEWORK.md](docs/CLI_FRAMEWORK.md) for:
- Complete API reference
- Profile configuration guide
- Custom command examples
- Advanced usage patterns
- Session management
- File operations and safety

See [examples/minimal_config/cli_profiles.yaml](examples/minimal_config/cli_profiles.yaml) for configuration examples.

## License

MIT
