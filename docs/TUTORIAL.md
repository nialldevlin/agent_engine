# Agent Engine Tutorial

A hands-on walkthrough of Agent Engine concepts using the Mini-Editor example application.

## Table of Contents

1. [Prerequisites & Setup](#prerequisites--setup)
2. [Core Concepts](#core-concepts)
3. [Your First Workflow](#your-first-workflow)
4. [Mini-Editor Example](#mini-editor-example)
5. [Advanced Patterns](#advanced-patterns)
6. [Debugging & Observability](#debugging--observability)

---

## Prerequisites & Setup

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/agent_engine.git
cd agent_engine

# Install in development mode
pip install -e .
```

### Verify Installation

```bash
python -c "from agent_engine import Engine; print('Agent Engine installed successfully')"
```

### API Keys

You'll need an Anthropic API key for LLM agent operations:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

---

## Core Concepts

### What is Agent Engine?

Agent Engine is a framework for executing complex workflows as Directed Acyclic Graphs (DAGs). Think of it like:

- **DAG** = Flowchart of your workflow
- **Node** = Single operation (deterministic or LLM-driven)
- **Task** = One execution of the workflow
- **Role** = Type of node (START, LINEAR, DECISION, BRANCH, SPLIT, MERGE, EXIT)

### Your First DAG

Here's the simplest possible workflow:

```yaml
nodes:
  - id: "start"
    kind: "deterministic"
    role: "start"
    default_start: true
    context: "none"

  - id: "process"
    kind: "agent"
    role: "linear"
    context: "global"
    tools: []

  - id: "exit"
    kind: "deterministic"
    role: "exit"
    context: "none"

edges:
  - from: "start"
    to: "process"
  - from: "process"
    to: "exit"
```

This workflow:
1. Starts at the START node
2. Passes to an agent node that can think
3. Ends at the EXIT node

---

## Your First Workflow

### Step 1: Create Configuration Directory

```bash
mkdir my_workflow
cd my_workflow
```

### Step 2: Define the Workflow (workflow.yaml)

Create `workflow.yaml`:

```yaml
version: "1.0"
description: "Simple analysis workflow"

nodes:
  - id: "start"
    kind: "deterministic"
    role: "start"
    default_start: true
    context: "none"
    continue_on_failure: false

  - id: "analyze"
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
    to: "analyze"
  - from: "analyze"
    to: "exit"
```

### Step 3: Configure Agents (agents.yaml)

Create `agents.yaml`:

```yaml
version: "1.0"
agents:
  - id: "main_agent"
    kind: "agent"
    llm: "anthropic/claude-3-5-sonnet"
    config:
      temperature: 0.7
      max_tokens: 1000
```

**How agents work:**
- Each agent has an `id` (e.g., "main_agent")
- Reference this id in `workflow.yaml` using `agent_id: "main_agent"`
- The `llm` field uses format `provider/model-name`
- The `config` section sets options like temperature and max_tokens

You can define multiple agents with different models and configurations, then use whichever you need in your workflow.

### Step 4: Configure Tools (tools.yaml)

Create `tools.yaml`:

```yaml
version: "1.0"
tools:
  - id: "read_file"
    type: "filesystem"
    entrypoint: "agent_engine.tools.filesystem:read_file"
    permissions:
      allow_network: false
      allow_shell: false
      root: false
```

### Step 5: Run the Engine

Create `test_workflow.py`:

```python
from agent_engine import Engine

# Load configuration
engine = Engine.from_config_dir(".")

# Run workflow
result = engine.run({
    "request": "analyze README.md"
})

print("Result:", result)

# Check events
events = engine.get_events()
print(f"Execution generated {len(events)} events")
```

Run it:

```bash
python test_workflow.py
```

### Step 6: Configure Credentials (provider_credentials.yaml)

Before running the engine, you need to configure how the engine loads API keys.

Create `provider_credentials.yaml`:

```yaml
version: "1.0"
provider_credentials:
  - id: "anthropic"
    provider: "anthropic"
    auth:
      type: "api_key"
      source: "env"
      env_var: "ANTHROPIC_API_KEY"
```

**Set your API key:**

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

**Verify it's set:**

```bash
echo $ANTHROPIC_API_KEY  # Should print your key
```

Your config directory should now look like:

```
my_workflow/
├── workflow.yaml
├── agents.yaml
├── tools.yaml
├── provider_credentials.yaml
└── test_workflow.py
```

Now when you run `python test_workflow.py`, the engine will load your API key and make LLM calls.

---

## Mini-Editor Example

The Mini-Editor demonstrates all core concepts. Let's walk through it:

### Structure Overview

```
examples/mini_editor/
├── run_mini_editor.py          # Entry point
├── cli_commands.py             # Custom CLI commands
├── config/
│   ├── workflow.yaml           # Main DAG
│   ├── agents.yaml             # LLM configurations
│   ├── tools.yaml              # Tools (read/write files)
│   ├── memory.yaml             # Memory stores
│   ├── cli_profiles.yaml       # CLI configuration
│   └── schemas/
│       └── document.json       # Document validation
└── README.md                   # Mini-editor documentation
```

### The Workflow

The mini-editor's DAG:

```
START
  ↓
normalize_request (deterministic)
  ↓
decide_operation (DECISION agent)
  ├─→ [create] draft_document
  └─→ [edit] edit_document
  ↓
generate_summary
  ↓
EXIT
```

Key features:

1. **normalize_request** - Validates and normalizes user input
2. **decide_operation** - DECISION node routes based on action (create/edit)
3. **draft_document** - Creates new document content
4. **edit_document** - Revises existing document
5. **generate_summary** - Creates document summary
6. **exit** - Returns final output

### Running Mini-Editor

```bash
cd examples/mini_editor

# Interactive mode (default)
python run_mini_editor.py

# Example mode
python run_mini_editor.py example

# From Python code
from agent_engine import Engine
engine = Engine.from_config_dir("config")
repl = engine.create_repl()
repl.run()
```

### Interactive Session Example

```bash
[default]> /create "My Document"

[Document Created]
Title: My Document
Status: success

[default]> /history

Session History:
1. [user] /create "My Document" - success

[default]> /quit
```

---

## Advanced Patterns

### Pattern 1: Decision Routing

Use DECISION nodes to route based on output:

```yaml
nodes:
  - id: "check"
    kind: "agent"
    role: "decision"
    context: "global"

  - id: "approve"
    kind: "agent"
    role: "linear"

  - id: "reject"
    kind: "agent"
    role: "linear"

edges:
  - from: "check"
    to: "approve"
    label: "approved"
  - from: "check"
    to: "reject"
    label: "rejected"
```

The agent outputs a decision (e.g., `{"decision": "approved"}`), which routes to the matching edge.

### Pattern 2: Branching & Cloning

Use BRANCH to create parallel task clones:

```yaml
nodes:
  - id: "start"
    kind: "deterministic"
    role: "start"
    default_start: true

  - id: "branch"
    kind: "agent"
    role: "branch"
    context: "global"

  - id: "process_a"
    kind: "agent"
    role: "linear"

  - id: "process_b"
    kind: "agent"
    role: "linear"

  - id: "merge"
    kind: "deterministic"
    role: "merge"

edges:
  - from: "start"
    to: "branch"
  - from: "branch"
    to: "process_a"
  - from: "branch"
    to: "process_b"
  - from: "process_a"
    to: "merge"
  - from: "process_b"
    to: "merge"
```

Execution:
1. BRANCH creates 2 clones
2. Both clones execute in parallel
3. Parent completes when first succeeds
4. MERGE aggregates both results

### Pattern 3: Subtask Parallelism

Use SPLIT for true parallelism where all tasks complete:

```yaml
nodes:
  - id: "split"
    kind: "deterministic"
    role: "split"

  - id: "process_1"
    kind: "agent"
    role: "linear"

  - id: "process_2"
    kind: "agent"
    role: "linear"

  - id: "merge"
    kind: "deterministic"
    role: "merge"

edges:
  - from: "split"
    to: "process_1"
  - from: "split"
    to: "process_2"
  - from: "process_1"
    to: "merge"
  - from: "process_2"
    to: "merge"
```

Execution:
1. SPLIT creates 2 subtasks
2. Parent task waits for all
3. Both subtasks execute in parallel
4. MERGE combines results

### Pattern 4: Context & Memory

Use memory stores to persist context:

```yaml
memory:
  task_store:
    type: "in_memory"
  project_store:
    type: "in_memory"
  context_profiles:
    - id: "default"
      max_tokens: 4000
      retrieval_policy: "recency"
      sources:
        - store: "task"
          tags: []
        - store: "project"
          tags: []
```

In your Python code:

```python
engine = Engine.from_config_dir("config")

# Store context
task_store = engine.get_memory_store("task")
task_store.add("document_id", "doc-001")

# Access in workflows
# Nodes with context: "global" will have doc-001 available
```

---

## Debugging & Observability

### Event Inspection

After running, inspect all events:

```python
engine = Engine.from_config_dir("config")
result = engine.run({"request": "test"})

# Get all events
events = engine.get_events()
for event in events:
    print(f"{event.timestamp} - {event.type}")

# Filter by type
node_events = engine.get_events_by_type("node_completed")

# Filter by task
task_events = engine.get_events_by_task(result["task_id"])
```

### Task History

Examine task execution history:

```python
from agent_engine import Engine

engine = Engine.from_config_dir("config")
result = engine.run({"request": "test"})

# Task object contains full execution history
task_id = result["task_id"]
print(f"Task {task_id}:")
print(f"  Status: {result['status']}")
print(f"  Output: {result['output']}")
```

### Telemetry Events

All major operations emit events:

```
task_started
├── node_started(start)
├── context_assembled
├── node_completed(start)
├── routing_decision
├── node_started(analyze)
├── tool_invoked(read_file)
├── tool_completed(read_file)
├── node_completed(analyze)
├── routing_decision
├── node_started(exit)
├── node_completed(exit)
└── task_completed
```

### Using Plugins for Observability

Create a custom plugin:

```python
from agent_engine.schemas import PluginBase, Event

class DebugPlugin(PluginBase):
    def on_event(self, event: Event) -> None:
        if event.type == "node_completed":
            print(f"Node {event.stage_id} completed successfully")
        elif event.type == "task_failed":
            print(f"Task {event.task_id} failed: {event.error}")

# Register in plugins.yaml
# plugins:
#   - id: debug
#     module: my_app.DebugPlugin
#     enabled: true
```

---

## Next Steps

1. **Explore Examples**: Check `examples/minimal_config/` and `examples/mini_editor/`
2. **Read Architecture**: See [ARCHITECTURE.md](ARCHITECTURE.md) for system design
3. **API Reference**: See [API_REFERENCE.md](API_REFERENCE.md) for complete API
4. **Build Your Workflow**: Use these patterns to create your own

## Tips & Best Practices

1. **Start Simple**: Begin with START → LINEAR → EXIT before adding branches
2. **Use Profiles**: Leverage context profiles to control token usage
3. **Validate Early**: Use schemas to catch errors early
4. **Monitor Events**: Subscribe to events for observability
5. **Test Workflows**: Create unit tests for your DAGs
6. **Version Configs**: Keep manifests in version control

## Troubleshooting

### "Config directory not found"

```bash
# Make sure workflow.yaml, agents.yaml, tools.yaml exist
ls config/workflow.yaml config/agents.yaml config/tools.yaml
```

### "No start node found"

```yaml
# Ensure exactly one node has default_start: true
- id: "start"
  role: "start"
  default_start: true  # <- Required
```

### "Tool not found"

```yaml
# Verify tool is defined in tools.yaml
# Verify node references it in workflow.yaml
- id: "process"
  tools: ["read_file"]  # <- Must be defined in tools.yaml
```

### "LLM invocation failed"

```bash
# Check API key is set
echo $ANTHROPIC_API_KEY

# Check network connectivity
curl https://api.anthropic.com/health
```

---

## Complete Example

Here's a complete, runnable example:

```python
from agent_engine import Engine
import tempfile
import os

# Create temporary config
with tempfile.TemporaryDirectory() as tmpdir:
    # workflow.yaml
    workflow = """
version: "1.0"
nodes:
  - id: "start"
    kind: "deterministic"
    role: "start"
    default_start: true
    context: "none"
  - id: "process"
    kind: "agent"
    role: "linear"
    context: "global"
    tools: []
  - id: "exit"
    kind: "deterministic"
    role: "exit"
    context: "none"
edges:
  - from: "start"
    to: "process"
  - from: "process"
    to: "exit"
"""
    with open(f"{tmpdir}/workflow.yaml", "w") as f:
        f.write(workflow)

    # agents.yaml
    agents = """
version: "1.0"
agents:
  - id: "default"
    kind: "agent"
    llm: "anthropic/claude-3-5-sonnet"
    config: {}
"""
    with open(f"{tmpdir}/agents.yaml", "w") as f:
        f.write(agents)

    # tools.yaml
    tools = """
version: "1.0"
tools: []
"""
    with open(f"{tmpdir}/tools.yaml", "w") as f:
        f.write(tools)

    # Run engine
    engine = Engine.from_config_dir(tmpdir)
    result = engine.run({"request": "hello"})
    print(f"Task: {result['task_id']}")
    print(f"Status: {result['status']}")
```

---

## See Also

- [Architecture Documentation](ARCHITECTURE.md)
- [API Reference](API_REFERENCE.md)
- [CLI Framework](CLI_FRAMEWORK.md)
- [Examples Directory](../examples/)
