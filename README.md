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

Defines read-only observer plugins for logging, metrics, and telemetry.

Plugins are loaded during initialization and receive notification events without modifying engine state.

Example:
```yaml
plugins:
  - id: "logger_plugin"
    module: "my_plugins.logger"
    config: {}
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

## Phase 2 Status

**Current Implementation:** Engine initialization and manifest loading.

**Available:**
- Manifest loading and validation for workflow, agents, tools, memory, and plugins
- DAG construction with adjacency structures and reachability analysis
- Comprehensive schema validation against canonical constraints
- Memory store initialization (stubs)
- Tool and LLM adapter registration
- Comprehensive error handling with detailed context
- Plugin system initialization

**Not Yet Implemented (Future Phases):**
- Workflow execution and node traversal (Phase 4)
- Memory retrieval and context assembly (Phase 6)
- Tool invocation and execution (Phase 4)
- LLM agent calls and reasoning (Phase 4)
- Decision routing and conditional branching (Phase 5)

The `Engine.run()` method currently returns an initialization stub confirming successful setup. Full execution will be implemented in Phase 4 and beyond.

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

## License

MIT
