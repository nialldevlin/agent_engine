LLM NOTICE: Do not modify this file unless explicitly instructed by the user.

# Agent Engine – Operational Guide

## Quick Start

### Installation

```bash
pip install -e .
```

### Basic Usage

```python
from agent_engine import Engine

# 1. Create the Engine from the configs directory
engine = Engine.from_config_dir(
    "configs/my_app",
    llm_client=YourLLMClient()
)

# 2. Run a task
result = engine.run_one("List Python files in src/", mode="implement")

# 3. Inspect results
print(result.status)
for stage_id, record in result.stage_results.items():
    print(f"{stage_id}: {record.output}")
print(f"Events emitted: {len(engine.telemetry.events)}")
```

Any real application should use `Engine` plus the schema types exported from `agent_engine` and should *not* import `agent_engine.runtime.*` directly.

## Public API

The Engine façade is the **only supported public entry point**. Applications, demos, and downstream services **must register tool handlers through `Engine.register_tool_handler`** and must not instantiate runtime components manually.

### Engine Methods

- `Engine.from_config_dir(config_dir: str, llm_client: LLMClient, *, telemetry: Optional[TelemetryBus] = None, plugins: Optional[PluginManager] = None) -> Engine`
- `engine.create_task(input: str | TaskSpec, *, mode: str | TaskMode = "default") -> Task`
- `engine.run_task(task: Task) -> Task`
- `engine.run_one(input: str | TaskSpec, mode: str | TaskMode = "default") -> Task`
- `engine.register_tool_handler(tool_id: str, handler: Callable[[Dict[str, Any]], Any]) -> None`

Running `from agent_engine import Engine` should always succeed, and runtime internals (for example `TaskManager`, `Router`, `PipelineExecutor`, `AgentRuntime`, `ToolRuntime`, `ContextAssembler`) are intentionally hidden from the package root.

## Configuration Surfaces

Agent Engine is entirely driven by manifests. When updating behavior, change the YAML/JSON files instead of touching runtime code:

1. `agents.yaml` — Agent definitions (model, tools, context profiles)
2. `tools.yaml` — Tool definitions (kind, schemas, permissions)
3. `stages.yaml` — Stage definitions (agent/tool stages, error policies)
4. `workflow.yaml` — Workflow graph (stages and edges)
5. `pipelines.yaml` — Pipeline definitions (entry/exit, allowed modes, fallbacks)
6. `memory.yaml` *(optional)* — Memory configuration (task/project/global stores, context policies)
7. `plugins.yaml` *(optional)* — Plugin manifest surface

All manifests are validated against the JSON schemas in `src/agent_engine/schemas/registry.py` and the Pydantic models in `src/agent_engine/schemas/`. Invalid manifests raise structured `EngineError` objects during `Engine.from_config_dir`.

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
├── tests/
│   └── test_end_to_end.py
├── pyproject.toml
└── README.md
```

### Example Apps

There is temporarily no canonical `examples/*` entry point because the engine is still shaping its runtime APIs. When an example returns, it must:

- Instantiate `Engine` via `Engine.from_config_dir`
- Use `engine.run_one`/`engine.create_task` + `engine.run_task`
- Register deterministic tool handlers via `Engine.register_tool_handler`
- Avoid direct imports from `agent_engine.runtime.*`

## Notes

- **No hard-coded behavior:** Agents, tools, and routing come from manifests.
- **Safe for long-lived processes:** `Engine.run_one()` keeps state in `TaskManager`; no global mutation occurs.
- **Structured errors:** Config/runtime failures surface as `EngineError`.
- **Telemetry and plugins:** `TelemetryBus` and `PluginManager` are pluggable via the `Engine` constructor.
