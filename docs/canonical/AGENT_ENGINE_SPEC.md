# LLM NOTICE: Do not modify this file unless explicitly instructed by the user.

# Agent Engine — Specification & Completion Requirements

## 1. Purpose & Scope

**Agent Engine** is a **general-purpose LLM orchestration engine**, not an application.

When finished, it must:

1. Execute **manifest-defined workflows** (DAGs of agents, tools, and routing logic).
2. Provide a **stable runtime** for multi-agent systems (agent runtime + tool runtime + memory + routing).
3. Be **configuration-driven** (no hard-coded app behavior in core).
4. Expose **telemetry & hook surfaces** so applications can add plugins, analytics, and advanced behaviors.
5. Support multiple LLM backends via a **pluggable LLM adapter**.

It must *not*:

* Hard-code specific applications (e.g., “code gremlin” behavior).
* Depend on any particular pattern (ReAct, committee, supervisor, etc.).
* Depend on a specific provider (must support multiple LLMs).

---

## 2. High-Level Architecture (What Must Exist)

The finished engine must have these major areas implemented and stable:

1. **Config & Manifest System**

   * YAML/JSON manifests for:

     * Agents
     * Tools
     * Workflows (DAG)
     * Pipelines (stage sequences)
     * Memory configuration & context profiles
     * Plugins & hooks
   * Schema registry + validation for all of the above.

2. **Workflow Graph & Pipeline Executor**

   * A DAG-based workflow model:

     * Node types: agent node, tool node, decision/branch node, etc.
     * Edge types: normal, error, conditional.
   * A pipeline executor that:

     * Walks the DAG for a given task.
     * For each node, runs a configurable stage pipeline.

3. **Runtime**

   * **Agent runtime** (LLM calls, prompt construction, JSON enforcement).
   * **Tool runtime** (deterministic tool invocation with safety).
   * **Task manager** (task lifecycle, ID, state).
   * **Router** (decides next node based on graph + task state).
   * **Context/memory runtime** (task/project/global memory).

4. **Memory & Context System**

   * Task-level, project-level, and optional global memory stores.
   * Configurable **context profiles** and retrieval policies.
   * A **ContextAssembler** that chooses what goes into prompts.

5. **JSON Engine**

   * Strict JSON validation for agent outputs and tool I/O.
   * Schema-driven repair and retry strategies.
   * Clear, structured error types.

6. **Telemetry & Event Bus**

   * Event types for:

     * agent calls
     * tool calls
     * workflow transitions
     * errors/failures
     * cost/usage
   * Event bus with pluggable sinks (file, stdout, custom plugins).

7. **Plugin & Hook System**

   * Hooks around key lifecycle points:

     * before/after task
     * before/after node
     * before/after agent call
     * before/after tool call
     * on error / on task completion
   * Plugin manager to register and configure plugins from manifests.

8. **LLM Adapter**

   * A common interface for LLM calls.
   * Support for multiple providers/models.
   * Token/counting & cost tracking.

9. **Patterns Library (Optional)**

   * Optional templates for common patterns (committee, supervisor, etc.).
   * Fully decoupled: engine runs fine with zero patterns loaded.

10. **Tests & Hardening**

    * Unit tests, integration tests, config/schema tests.
    * Example project tests.
    * Basic performance & reliability checks.

---

## 3. Definition of Done (Completion Criteria)

The engine is “complete” when all of the following are true:

### 3.1 Config & Manifests

* ✅ All engine behavior is driven by manifests:

  * No hard-coded agents/tools/workflows in `src/agent_engine` core.
* ✅ Schema registry exists for all config surfaces and is used at load time.
* ✅ Invalid manifests produce clear, structured errors (not silent failure).
* ✅ Example configs (`configs/basic_llm_agent`) validate against the same schemas.

### 3.2 Workflow & Pipeline Executor

* ✅ A workflow can be fully described in `workflow.yaml` and `pipelines.yaml` with no code changes.
* ✅ The DAG is validated (no cycles, valid node/edge types).
* ✅ The engine can:

  * Start at a configured entry node.
  * Execute through multiple nodes.
  * Handle conditional edges based on node results.

### 3.3 Runtime (Agent, Tool, Task, Router)

* ✅ **AgentRuntime**:

  * Builds prompts deterministically.
  * Calls LLM via LLM adapter.
  * Enforces JSON output via JSON engine.
  * Surfaces errors with clear types (no generic “oops”).

* ✅ **ToolRuntime**:

  * Executes only tools declared in manifests.
  * Enforces configured permissions (filesystem root, commands, etc.).
  * Logs tool calls via telemetry.

* ✅ **TaskManager**:

  * Creates tasks with unique IDs.
  * Tracks node progress & results.
  * Can resume tasks or inspect history.

* ✅ **Router**:

  * Respects the workflow DAG.
  * Uses node outputs to pick next edges when conditional.
  * Handles error paths and fallback nodes.

### 3.4 Memory & Context

* ✅ Memory tiers implemented:

  * TaskStore (per-task history/state).
  * ProjectStore (longer-lived project context).
  * GlobalStore (optional, engine or app-level).

* ✅ ContextAssembler:

  * Reads memory according to context profiles.
  * Applies retrieval policies (e.g., recency or hybrid scoring).
  * Performs token budgeting to stay under model limits.

### 3.5 JSON Engine

* ✅ All agent outputs that should be JSON are validated against their schemas.
* ✅ JSON errors are categorized (parse vs schema vs catastrophic).
* ✅ Engine retries in a controlled way (no infinite loops).
* ✅ Tools using JSON IO also pass through JSON Engine where applicable.

### 3.6 Telemetry & Events

* ✅ Every agent and tool call produces telemetry events with:

  * timestamps
  * task ID
  * node ID
  * latency
  * model info (for agents)
  * cost/usage (when available)

* ✅ Workflow transitions produce events.

* ✅ Errors and retries are logged as events.

* ✅ Telemetry sinks (at least JSONL file) can be configured via manifests.

### 3.7 Plugin System

* ✅ Hooks exist and are exercised in at least one example plugin.

* ✅ Plugins are loaded from manifests (`plugins.yaml`).

* ✅ Plugins can subscribe to events and/or hooks to:

  * log
  * add metrics
  * alter behavior in controlled ways

* ✅ The engine runs with **zero plugins configured**.

### 3.8 LLM Adapter

* ✅ A base `LLMClient` interface exists.
* ✅ At least:

  * one OpenAI-compatible adapter
  * one Anthropic-compatible adapter
* ✅ Callers (AgentRuntime) do not depend on provider-specific details.
* ✅ Token and cost estimation is recorded in telemetry where possible.

### 3.9 Patterns Library (Optional but Clean)

* ✅ `patterns/` contains example patterns (committee, supervisor, etc.) implemented using engine APIs.
* ✅ No core engine code imports patterns.
* ✅ Patterns are wired via manifests, not hard-coded.

### 3.10 Tests & Examples

* ✅ `tests/` covers:

  * config & schema loading/validation
  * workflow execution (at least one non-trivial DAG)
  * agent runtime and tool runtime
  * memory & context policies
  * telemetry + plugin integration
  * example applications

* ✅ No “empty” tests that just `pass` or only import modules.

* ✅ `examples/basic_llm_agent` is a working example:

  * Can be run from CLI.
  * Uses only engine surfaces (no secret internal hacks).

When all of the above are true, the engine is “ready for serious apps.”

---

## 4. What an Example Project Should Look Like

This section defines what a **well-formed Agent Engine application** looks like once the engine is complete.

### 4.1 Directory structure

Example: a “Code Gremlin” project generator app.

```text
code_gremlin/
├── configs
│   ├── agents.yaml
│   ├── tools.yaml
│   ├── memory.yaml
│   ├── plugins.yaml
│   ├── workflow.yaml
│   └── pipelines.yaml
├── src
│   ├── code_gremlin
│   │   ├── cli.py
│   │   └── __init__.py
│   └── tools
│       └── code_ops.py
├── pyproject.toml
├── README.md
└── tests
    └── test_end_to_end.py
```

The application:

* Depends on `agent_engine` as a library.
* Defines configurations and minimal glue code.

### 4.2 Example `agents.yaml`

```yaml
agents:
  project_architect:
    model: "gpt-max"
    description: "Designs the project architecture and file layout."
    context_profile: "architect_profile"
    tools: []
    output_schema: "ArchitectOutput"

  module_implementer:
    model: "claude-sonnet"
    description: "Implements code modules using filesystem and test tools."
    context_profile: "implementation_profile"
    tools:
      - write_file
      - read_file
      - run_tests
    output_schema: "ImplementerOutput"

  code_reviewer:
    model: "gpt-max"
    description: "Reviews code and suggests improvements."
    context_profile: "review_profile"
    tools: []
    output_schema: "ReviewerOutput"
```

### 4.3 Example `tools.yaml`

```yaml
tools:
  write_file:
    type: filesystem.write_file
    root: "./generated_project"

  read_file:
    type: filesystem.read_file
    root: "./generated_project"

  list_files:
    type: filesystem.list
    root: "./generated_project"

  run_tests:
    type: command.run
    command: "pytest --maxfail=1"
    working_dir: "./generated_project"
```

These tools are implemented generically by Agent Engine’s tool runtime, with safety boundaries derived from these configs.

### 4.4 Example `workflow.yaml`

```yaml
workflow:
  nodes:
    - id: gather_requirements
      type: agent
      agent: project_architect

    - id: design_architecture
      type: agent
      agent: project_architect

    - id: implement_module
      type: agent
      agent: module_implementer

    - id: review_module
      type: agent
      agent: code_reviewer

    - id: finalize_project
      type: agent
      agent: module_implementer

  edges:
    - from: gather_requirements
      to: design_architecture

    - from: design_architecture
      to: implement_module

    - from: implement_module
      to: review_module

    - from: review_module
      to: implement_module
      condition: "changes_requested"

    - from: review_module
      to: finalize_project
      condition: "approved"
```

Engine reads this DAG and pipeline definitions to drive everything.

### 4.5 Example `pipelines.yaml`

```yaml
pipeline_templates:
  agent_node:
    stages:
      - load_task_state
      - assemble_context
      - build_prompt
      - call_llm
      - validate_json
      - apply_agent_effects   # e.g., tool calls if the schema says so
      - emit_telemetry

  tool_node:
    stages:
      - validate_tool_input
      - execute_tool
      - emit_telemetry
```

These stage names correspond to functions/methods in engine runtime.

### 4.6 Example `memory.yaml`

```yaml
memory:
  task_store:
    type: in_memory
    max_messages: 20

  project_store:
    type: file_json
    path: "./.project_memory.json"

  global_store:
    type: disabled

context_profiles:
  architect_profile:
    max_tokens: 4000
    retrieval_policy: "hybrid"
    sources:
      - task_store

  implementation_profile:
    max_tokens: 6000
    retrieval_policy: "recency"
    sources:
      - task_store
      - project_store

  review_profile:
    max_tokens: 4000
    retrieval_policy: "recency"
    sources:
      - task_store
      - project_store
```

### 4.7 Example `plugins.yaml`

```yaml
plugins:
  - name: jsonl_telemetry_logger
    type: telemetry.logger
    config:
      path: "./logs/events.jsonl"

  - name: cost_summary
    type: telemetry.cost_summary
    config:
      warn_above_usd: 0.10
```

### 4.8 Example `src/code_gremlin/cli.py`

```python
from agent_engine import Engine

def main():
    engine = Engine.from_config_dir("configs")
    result = engine.run()
    print("Project generated at:", result.output_path)
    print("Summary:\n", result.summary)

if __name__ == "__main__":
    main()
```

That’s all the “code” needed to hook into the engine for a non-trivial app.

---

## 5. How Suites (Claude / GPT-Max) Should Think About “Done”

When agent suites are building Agent Engine, they should aim for:

1. **Engine equals platform, not app.**

   * Code under `src/agent_engine` knows nothing about “code gremlins”, “doc assistants”, etc.
   * It only knows about **agents, tools, workflows, tasks, memory, plugins, telemetry**.

2. **Everything interesting lives in manifests + plugins.**

   * Adding a new app = **add configs + optional tools/plugins**, do not touch engine core.

3. **Example apps prove capability.**

   * At least one fully working example (like `basic_llm_agent` now; later a `code_gremlin`), driven purely by configs.

4. **Tests validate engine, not specific apps.**

   * Tests in `tests/` confirm:

     * DAG execution
     * agent & tool runtime
     * schemas & config loading
     * memory & routing
     * plugin/hook behaviors

If those principles hold and all “Definition of Done” items above are satisfied, you’ve got a real Agent Engine that can host your chaos gremlins safely.
