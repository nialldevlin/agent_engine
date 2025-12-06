# Phase 0: Implementation Brief for Qwen2.5-coder 7B

## Overview

This brief defines the step-by-step implementation plan for **Phase 0 – Repo Cleanup, Guardrails, and Public API Shell**. Each step is sized for a single focused Qwen task with explicit file-level changes, schema/interface details, integration points, and test requirements.

---

## Context Summary

**Current State:**
- Runtime components exist and are functional: `TaskManager`, `Router`, `PipelineExecutor`, `AgentRuntime`, `ToolRuntime`, `ContextAssembler`
- `config_loader.py` has `load_engine_config()` returning `EngineConfig` dataclass
- Example app (`examples/basic_llm_agent/cli.py`) manually wires all components
- `__init__.py` is nearly empty (only exports `__version__`)

**Goal:**
Create a stable `Engine` façade that:
- Provides a clean public API for applications
- Hides runtime implementation details
- Supports `from_config_dir()`, `create_task()`, `run_task()`, `run_one()` methods
- Is the **only** public entry point (apps should not import `runtime.*` directly)

---

## Step 1: Create Engine Façade Skeleton

**File:** `src/agent_engine/engine.py` (new file)

**What to implement:**

Create a new `Engine` class with these methods:

```python
class Engine:
    def __init__(
        self,
        config: EngineConfig,
        llm_client: LLMClient,
        telemetry: Optional[TelemetryBus] = None,
        plugins: Optional[PluginManager] = None
    ):
        # Store config and clients
        # Initialize runtime components:
        #   - self.task_manager = TaskManager()
        #   - self.router = Router(workflow=config.workflow, pipelines=config.pipelines, stages=config.stages)
        #   - self.context_assembler = ContextAssembler(memory_config=config.memory)
        #   - self.agent_runtime = AgentRuntime(llm_client=llm_client)
        #   - self.tool_runtime = ToolRuntime(tools=config.tools, tool_handlers={})
        #   - self.pipeline_executor = PipelineExecutor(...)
        #   - self.telemetry = telemetry or TelemetryBus()
        #   - self.plugins = plugins
        pass

    @classmethod
    def from_config_dir(
        cls,
        config_dir: str,
        llm_client: LLMClient,
        *,
        telemetry: Optional[TelemetryBus] = None,
        plugins: Optional[PluginManager] = None
    ) -> Engine:
        # 1. Build manifest dict from config_dir
        # 2. Call load_engine_config(manifests)
        # 3. Check for error, raise if present
        # 4. Return Engine(config, llm_client, telemetry, plugins)
        pass

    def create_task(
        self,
        input: str | TaskSpec,
        *,
        mode: str | TaskMode = "default"
    ) -> Task:
        # 1. If input is str, create TaskSpec with task_spec_id=auto-generated, request=input
        # 2. If mode is str, convert to TaskMode enum (default="analysis_only")
        # 3. Choose pipeline via router.choose_pipeline(spec)
        # 4. Create task via task_manager.create_task(spec, pipeline_id)
        # 5. Return Task
        pass

    def run_task(self, task: Task) -> Task:
        # 1. Call pipeline_executor.run(task, task.pipeline_id)
        # 2. Return updated Task
        pass

    def run_one(
        self,
        input: str | TaskSpec,
        mode: str | TaskMode = "default"
    ) -> Task:
        # Convenience: create_task() then run_task()
        pass
```

**Key Classes/Functions:**
- `Engine` class with 4 public methods + 1 classmethod
- Internal wiring of all runtime components in `__init__`

**Imports needed:**
```python
from pathlib import Path
from typing import Optional
from agent_engine.config_loader import load_engine_config, EngineConfig
from agent_engine.runtime.task_manager import TaskManager
from agent_engine.runtime.router import Router
from agent_engine.runtime.context import ContextAssembler
from agent_engine.runtime.agent_runtime import AgentRuntime
from agent_engine.runtime.tool_runtime import ToolRuntime
from agent_engine.runtime.pipeline_executor import PipelineExecutor
from agent_engine.runtime.llm_client import LLMClient
from agent_engine.schemas import Task, TaskSpec, TaskMode
from agent_engine.telemetry import TelemetryBus
from agent_engine.plugins import PluginManager
```

**Invariants:**
- `Engine` must be stateless with respect to tasks (all state in TaskManager)
- `run_one()` must be safe to call multiple times in a long-lived process
- No hard-coded behavior; everything from manifests

**Integration Points:**
- Uses `load_engine_config()` from `config_loader.py`
- Wires existing runtime components together
- Delegates all execution to `PipelineExecutor`

**Tests:** None yet (Step 6)

**Edge Cases:**
- `config_dir` doesn't exist → propagate error from `load_engine_config()`
- Invalid manifests → propagate error from `load_engine_config()`
- Mode string not in TaskMode enum → default to ANALYSIS_ONLY or raise clear error
- Tool handlers: for Phase 0, pass empty dict `{}` to ToolRuntime (apps will register later)

**Notes for Qwen:**
- This is a thin wrapper; delegate immediately to existing components
- Do NOT implement new logic; just wire what exists
- If a runtime component needs an argument you don't have, use a sensible default (e.g., empty dict for tool_handlers)

---

## Step 2: Update Public API Exports

**File:** `src/agent_engine/__init__.py` (edit)

**What to implement:**

Replace current content with:

```python
"""Agent Engine package root."""

from agent_engine.engine import Engine
from agent_engine.schemas import (
    # Core workflow types
    Task,
    TaskSpec,
    TaskMode,
    TaskStatus,
    # Agent and Tool definitions
    AgentDefinition,
    ToolDefinition,
    # Workflow and Pipeline
    WorkflowGraph,
    Pipeline,
    Edge,
    Stage,
    # Memory and Context
    MemoryConfig,
    ContextRequest,
    # Errors and Events
    EngineError,
    Event,
)

__all__ = [
    "Engine",
    # Types for manifests/specs
    "Task",
    "TaskSpec",
    "TaskMode",
    "TaskStatus",
    "AgentDefinition",
    "ToolDefinition",
    "WorkflowGraph",
    "Pipeline",
    "Edge",
    "Stage",
    "MemoryConfig",
    "ContextRequest",
    "EngineError",
    "Event",
    "__version__",
]

__version__ = "0.0.1"
```

**Invariants:**
- **Only** `Engine` and schema types are exported
- No runtime internals (`TaskManager`, `Router`, etc.) should leak
- Apps must use `Engine` and read/inspect schemas, but not construct runtime objects directly

**Integration Points:**
- Re-exports schemas from `agent_engine.schemas`
- Re-exports `Engine` from `agent_engine.engine`

**Tests:** Step 7 (import test)

**Edge Cases:**
- Avoid circular imports: `engine.py` imports from schemas, `__init__.py` imports from both

---

## Step 3: Add Docstrings to Engine Class

**File:** `src/agent_engine/engine.py` (edit)

**What to implement:**

Add comprehensive docstrings to `Engine` class and all methods:

```python
class Engine:
    """Agent Engine orchestrator façade.
    
    The Engine is the single public entry point for running manifest-driven
    multi-agent workflows. It loads configurations, manages task lifecycle,
    and executes workflows through a pipeline of agents and tools.
    
    Example apps should ONLY use Engine and public schemas; do not import
    runtime.* modules directly.
    
    Attributes:
        config (EngineConfig): Loaded configuration (agents, tools, workflow, etc.)
        llm_client (LLMClient): LLM backend adapter
        telemetry (TelemetryBus): Event telemetry bus
        plugins (PluginManager): Optional plugin system
    """

    @classmethod
    def from_config_dir(
        cls,
        config_dir: str,
        llm_client: LLMClient,
        *,
        telemetry: Optional[TelemetryBus] = None,
        plugins: Optional[PluginManager] = None
    ) -> Engine:
        """Create Engine from a configuration directory.
        
        The config_dir must contain YAML/JSON manifests:
        - agents.yaml: Agent definitions
        - tools.yaml: Tool definitions
        - stages.yaml: Stage definitions
        - workflow.yaml: Workflow graph (DAG)
        - pipelines.yaml: Pipeline definitions
        - memory.yaml: Memory configuration (optional)
        
        Args:
            config_dir: Path to directory containing manifests
            llm_client: LLM backend client implementing LLMClient interface
            telemetry: Optional telemetry bus for events/logging
            plugins: Optional plugin manager for hooks
            
        Returns:
            Configured Engine instance
            
        Raises:
            SystemExit or Exception: If config loading fails
            
        Example:
            >>> from agent_engine import Engine
            >>> engine = Engine.from_config_dir(
            ...     "configs/my_app",
            ...     llm_client=MyLLMClient()
            ... )
        """
        pass

    def create_task(
        self,
        input: str | TaskSpec,
        *,
        mode: str | TaskMode = "default"
    ) -> Task:
        """Create a new Task from user input.
        
        Args:
            input: Either a raw string request or a fully-formed TaskSpec
            mode: Execution mode (analysis_only, implement, review, dry_run)
                  Defaults to "analysis_only" if "default" is passed
                  
        Returns:
            Task object ready to execute
            
        Example:
            >>> task = engine.create_task("List all Python files", mode="implement")
        """
        pass

    def run_task(self, task: Task) -> Task:
        """Execute a Task through its configured pipeline.
        
        Args:
            task: Task object (from create_task)
            
        Returns:
            Updated Task with results, status, and routing trace
            
        Example:
            >>> task = engine.create_task("Analyze README.md")
            >>> result = engine.run_task(task)
            >>> print(result.status)
        """
        pass

    def run_one(
        self,
        input: str | TaskSpec,
        mode: str | TaskMode = "default"
    ) -> Task:
        """Convenience method: create and run a task in one call.
        
        Equivalent to:
            task = engine.create_task(input, mode=mode)
            return engine.run_task(task)
            
        Args:
            input: Either a raw string request or TaskSpec
            mode: Execution mode
            
        Returns:
            Completed Task with results
            
        Example:
            >>> result = engine.run_one("Fix the broken test")
        """
        pass
```

**Key Functions:**
- Add module-level docstring
- Add class-level docstring with attributes
- Add method docstrings with Args/Returns/Raises/Example

**Invariants:**
- Docstrings must follow Google style (Args/Returns/Raises/Example)
- Must explicitly state "apps should only use Engine" in class docstring

**Tests:** None (documentation only)

---

## Step 4: Update Operational Documentation

**File:** `docs/operational/README.md` (edit)

**What to implement:**

Add or replace sections:

```markdown
# Agent Engine – Operational Guide

## Quick Start

### Installation

```bash
pip install -e .
```

### Basic Usage

```python
from agent_engine import Engine

# 1. Create engine from config directory
engine = Engine.from_config_dir(
    "configs/basic_llm_agent",
    llm_client=YourLLMClient()
)

# 2. Run a task
result = engine.run_one("List Python files in src/", mode="implement")

# 3. Inspect results
print(result.status)
for stage_id, record in result.stage_results.items():
    print(f"{stage_id}: {record.output}")
```

## Public API

### Engine Class

The `Engine` is the **only public entry point**. Example applications must use `Engine` and public schemas; **do not import `runtime.*` modules directly**.

**Methods:**
- `Engine.from_config_dir(config_dir, llm_client, *, telemetry, plugins)`: Create Engine from manifests
- `engine.create_task(input, *, mode)`: Create Task from string or TaskSpec
- `engine.run_task(task)`: Execute Task through pipeline
- `engine.run_one(input, mode)`: Convenience: create + run in one call

**Example Apps:**
- See `examples/basic_llm_agent/` for a working example
- Apps should **only** import from `agent_engine` (not `agent_engine.runtime`)

## Configuration Surfaces

Agent Engine is fully configuration-driven. All behavior comes from YAML/JSON manifests:

1. **agents.yaml**: Agent definitions (model, tools, context profiles)
2. **tools.yaml**: Tool definitions (type, permissions, schemas)
3. **stages.yaml**: Stage definitions (agent/tool stages, error policies)
4. **workflow.yaml**: Workflow graph (DAG of stages and edges)
5. **pipelines.yaml**: Pipeline definitions (entry/exit nodes, modes)
6. **memory.yaml**: Memory configuration (task/project/global stores, context profiles)
7. **plugins.yaml** (optional): Plugin configuration

All manifests are validated against JSON Schemas at load time. Invalid configs produce structured `EngineError` objects.

For schema details, see:
- `src/agent_engine/schemas/` for Pydantic model definitions
- `src/agent_engine/schemas/registry.py` for JSON Schema registry

## Example Directory Structure

```
my_agent_app/
├── configs/
│   ├── agents.yaml
│   ├── tools.yaml
│   ├── stages.yaml
│   ├── workflow.yaml
│   ├── pipelines.yaml
│   └── memory.yaml
├── src/
│   └── my_app/
│       └── cli.py
├── pyproject.toml
└── README.md
```

## Notes

- **No Hard-Coded Behavior**: Engine core has no app-specific logic
- **Safe for Long-Lived Processes**: `run_one()` is stateless (task state in TaskManager)
- **Error Handling**: All config/runtime errors return structured `EngineError` objects
```

**Key Sections:**
- Quick Start with code example
- Public API boundary (Engine only)
- Config surfaces list
- Example directory structure

**Invariants:**
- Must explicitly state "do not import runtime modules"
- Must point to schemas and validation

**Tests:** None (documentation only)

**Integration Points:**
- References `examples/basic_llm_agent/`
- References schemas in `src/agent_engine/schemas/`

---

## Step 5: Refactor Example CLI to Use Engine

**File:** `examples/basic_llm_agent/cli.py` (edit)

**What to implement:**

Replace the manual wiring in `build_example_components()` and `run_example()` with Engine usage:

**Before (current):**
```python
def build_example_components():
    # Manual wiring of 7+ components...
    task_manager = TaskManager()
    router = Router(...)
    # etc.
```

**After (refactored):**
```python
def run_example(user_request: str):
    # 1. Create LLM client
    llm_client = ExampleLLMClient()
    
    # 2. Create Engine from config directory
    engine = Engine.from_config_dir(
        str(CONFIG_DIR),
        llm_client=llm_client
    )
    
    # 3. Register tool handlers (if Engine exposes this)
    # For Phase 0, skip tool handlers or add a helper method to Engine
    
    # 4. Run task
    task = engine.run_one(user_request, mode="implement")
    
    # 5. Print results
    print(f"Task status: {task.status.value}")
    for stage_id, rec in task.stage_results.items():
        print(f"- {stage_id}: output={rec.output}")
```

**Key Changes:**
- Remove `build_example_components()` function entirely
- Replace manual wiring with `Engine.from_config_dir()`
- Use `engine.run_one()` instead of manual `create_task()` + `executor.run()`
- Keep `ExampleLLMClient` as-is
- Tool handlers: **For Phase 0**, either:
  - Skip tool registration (tools will fail at runtime, which is OK for this step), OR
  - Add a temporary `engine.register_tool_handler(name, fn)` method to Engine

**Invariants:**
- Example must use **only** `Engine` API (no `TaskManager`, `Router`, etc.)
- Must work with existing test in `tests/test_basic_llm_agent_example.py`

**Integration Points:**
- Imports `Engine` from `agent_engine`
- Continues to use `ExampleLLMClient` and tool handlers

**Tests:** Existing test `tests/test_basic_llm_agent_example.py` must still pass

**Edge Cases:**
- Tool handlers: Phase 0 may not have a clean API for this yet; document as known limitation or add quick helper method

**Note for Qwen:**
- This step may reveal that `Engine` needs a `register_tool_handler(name, fn)` helper
- If so, add it to `engine.py` as a simple passthrough to `self.tool_runtime.register_handler()`

---

## Step 6: Add Engine Runtime Tests

**File:** `tests/test_runtime.py` (edit/extend)

**What to implement:**

Add new test function:

```python
def test_engine_from_config_dir_runs_basic_llm_agent():
    """Test that Engine can load basic_llm_agent config and run a task.
    
    This test verifies:
    - Engine.from_config_dir() loads manifests correctly
    - Engine.run_one() executes a simple task
    - Result has expected status and stage results
    - Behavior matches existing manual-wired test
    """
    from agent_engine import Engine
    from pathlib import Path
    
    # Use the same ExampleLLMClient from basic_llm_agent
    from examples.basic_llm_agent.cli import ExampleLLMClient
    
    config_dir = Path(__file__).parent.parent / "configs" / "basic_llm_agent"
    
    engine = Engine.from_config_dir(
        str(config_dir),
        llm_client=ExampleLLMClient()
    )
    
    # Run a simple task
    task = engine.run_one("list files", mode="implement")
    
    # Verify results
    assert task.status.value in ["completed", "failed"]
    assert len(task.stage_results) > 0
    assert task.pipeline_id is not None
```

**Invariants:**
- Test must use **only** `Engine` API
- Test should mirror behavior of `test_basic_llm_agent_example.py`
- Must assert task status, stage results, pipeline_id

**Integration Points:**
- Uses `Engine.from_config_dir()`
- Uses `ExampleLLMClient` from example app
- Validates against existing config in `configs/basic_llm_agent/`

**Edge Cases:**
- Config not found → test should fail clearly
- Invalid manifest → test should fail clearly

---

## Step 7: Add Import Boundary Tests

**File:** `tests/test_imports.py` (edit/extend)

**What to implement:**

Add new test functions:

```python
def test_engine_import():
    """Verify Engine can be imported from top-level package."""
    from agent_engine import Engine
    assert Engine is not None

def test_public_api_exports():
    """Verify only approved types are exported from agent_engine."""
    import agent_engine
    
    # These MUST be exported
    required = [
        "Engine",
        "Task",
        "TaskSpec",
        "TaskMode",
        "AgentDefinition",
        "ToolDefinition",
        "WorkflowGraph",
        "Pipeline",
        "__version__",
    ]
    
    for name in required:
        assert hasattr(agent_engine, name), f"Missing required export: {name}"

def test_no_runtime_leaks():
    """Verify runtime internals are NOT exported from top-level."""
    import agent_engine
    
    # These should NOT be accessible from top-level
    forbidden = [
        "TaskManager",
        "Router",
        "PipelineExecutor",
        "AgentRuntime",
        "ToolRuntime",
        "ContextAssembler",
    ]
    
    for name in forbidden:
        assert not hasattr(agent_engine, name), f"Internal {name} should not be exported"
```

**Invariants:**
- `Engine` must be importable from `agent_engine`
- All public schema types must be importable
- Runtime internals must NOT be importable from top-level

**Integration Points:**
- Validates `__init__.py` exports
- Ensures API boundary is enforced

---

## Step 8: Add Tool Handler Registration (if needed)

**File:** `src/agent_engine/engine.py` (edit)

**What to implement:**

If Step 5 reveals the need, add a helper method:

```python
class Engine:
    # ... existing methods ...
    
    def register_tool_handler(self, tool_name: str, handler_fn):
        """Register a Python function to handle a tool.
        
        Args:
            tool_name: Tool ID from tools.yaml
            handler_fn: Callable taking dict input, returning dict output
            
        Example:
            >>> def my_handler(input_dict):
            ...     return {"result": "success"}
            >>> engine.register_tool_handler("my_tool", my_handler)
        """
        if not hasattr(self, 'tool_runtime'):
            raise RuntimeError("Engine not initialized")
        
        if not hasattr(self.tool_runtime, 'tool_handlers'):
            self.tool_runtime.tool_handlers = {}
        
        self.tool_runtime.tool_handlers[tool_name] = handler_fn
```

**Only implement this if:**
- Step 5 cannot be completed without it, OR
- Test in Step 6 cannot pass without it

**Invariants:**
- Must be safe to call multiple times
- Must raise clear error if called before Engine is initialized

**Tests:** Extend Step 6 test to call `register_tool_handler()` if implemented

**Note for Qwen:**
- This is OPTIONAL
- Only add if absolutely necessary for Phase 0
- Prefer minimal changes to existing ToolRuntime

---

## Implementation Order

Execute steps sequentially in this order:

1. **Step 1**: Create Engine façade skeleton
2. **Step 2**: Update `__init__.py` exports
3. **Step 3**: Add docstrings to Engine
4. **Step 4**: Update operational docs
5. **Step 5**: Refactor example CLI to use Engine
6. **Step 8** (conditional): Add tool handler registration if Step 5 needs it
7. **Step 6**: Add Engine runtime tests
8. **Step 7**: Add import boundary tests

**Checkpoint after each step:**
- Run `pytest tests/test_imports.py` after Step 2
- Run `pytest tests/test_basic_llm_agent_example.py` after Step 5
- Run `pytest tests/test_runtime.py` after Step 6
- Run full test suite after Step 7

---

## Success Criteria

Phase 0 is complete when:

- ✅ `Engine` class exists in `src/agent_engine/engine.py`
- ✅ `from agent_engine import Engine` works
- ✅ `Engine.from_config_dir()` loads configs and returns working Engine
- ✅ `engine.run_one()` executes tasks
- ✅ Example app (`examples/basic_llm_agent/cli.py`) uses only `Engine` API
- ✅ `tests/test_runtime.py` has `test_engine_from_config_dir_runs_basic_llm_agent()`
- ✅ `tests/test_imports.py` validates public API boundary
- ✅ All existing tests still pass
- ✅ `docs/operational/README.md` documents Engine usage

---

## Known Limitations & Future Work

Phase 0 deliberately does NOT address:

- **Tool handler registration API**: May need refinement in Phase 1
- **Plugin loading from manifests**: Engine accepts `plugins` param but doesn't load from `plugins.yaml` yet
- **Advanced routing**: Router uses simple heuristics; no telemetry-based routing yet
- **Telemetry configuration**: Telemetry is instantiated with defaults; no manifest-driven sinks yet
- **LLM client configuration**: Apps must instantiate `LLMClient` themselves; no factory yet

These are intentional deferments to keep Phase 0 focused on the façade and API boundary.
