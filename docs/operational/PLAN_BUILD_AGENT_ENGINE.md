# LLM NOTICE: Do not modify this file unless explicitly instructed by the user.

# **PLAN_AGENT_ENGINE — Clean, Engine-First, GPT-Max/Claude-Ready**

> **Purpose:** Produce a complete, production-ready Agent Engine as described in **AGENT_ENGINE_OVERVIEW.md**, using RESEARCH.md as design grounding and salvaging selected legacy utilities from king_arthur_orchestrator.
>
> **Design Philosophy:**
>
> * Build a **modular engine**, not an AI application.
> * Keep *core engine* minimal, stable, interchangeable.
> * Advanced features belong to **plugins, patterns, templates**, NOT core.
> * Everything configuration-driven.
> * DAG workflows, agent runtime, tool runtime, context/memory, routing, JSON engine, telemetry/event bus, plugin hooks, LLM adapter.
> * Avoid opinionated patterns (ReAct, challengers, post-mortem) in core.

---

# ✔ **Completed Foundations (Acknowledged)**

These areas are already complete or partially complete and must be **respected, not rebuilt**:

1. **Project Architecture + Engine Overview**

   * AGENT_ENGINE_OVERVIEW.md defines the authoritative structure.

2. **Legacy Salvage List Identified**

   * The following files are approved for salvage (light refactor only):

     ```
     legacy/
     └── king_arthur/src/king_arthur_orchestrator
         ├── core
         │   ├── manifest_hygiene.py
         │   ├── override_manager.py
         │   └── override_parser.py
         ├── json_engine
         │   ├── contracts.py
         │   ├── gateway.py
         │   ├── medic.py
         │   ├── utils.py
         └── toolkit
             ├── context.py
             ├── execution.py
             ├── file_context.py
             ├── filesystem.py
             ├── json_io.py
             ├── json_utils.py
             ├── log_utils.py
             ├── manifest_utils.py
             ├── plan_validation.py
             ├── prompt_helpers.py
             ├── registry.py
             ├── task_intent.py
             ├── text_analysis.py
             ├── token_utils.py
             ├── validation_utils.py
             └── version_utils.py
     ```

3. **Research Baseline Completed**

   * Retrieval, context, memory, routing, JSON handling, schema enforcement, plugin systems, etc.

---

# ✅ **Phase 0 — Salvage & Refactor Legacy Components (Engine-Safe Only) COMPLETE**

**Objective:** Extract, rename, and refactor *generic, engine-agnostic* utilities from Arthur’s toolkit into proper Agent Engine modules.

**0.1 Salvage JSON Engine**

* From `json_engine/*`
* Incorporate into new `agent_engine/json_engine/`
* Implement:

  * Structured EngineError hierarchy
  * Schema enforcement
  * Repair strategies
  * Retry logic
  * Normalization utilities
* Remove all Arthur-specific names and assumptions.

**0.2 Salvage Manifest & Registry Utilities**

* From `manifest_utils.py`, `registry.py`, `manifest_hygiene.py`
* Migrate to `agent_engine/config/manifest_loader.py`
* Support:

  * Agents
  * Tools
  * Pipelines (workflow graphs)
  * Context profiles
  * Plugins
  * Schemas and versioning

**0.3 Salvage Override Manager (Optional for Core)**

* From `override_manager.py`, `override_parser.py`
* Move to `agent_engine/runtime/overrides/`
* Make strictly:

  * Opt-in
  * Configurable
  * Manifest-driven
* No hard-coded commands or roles.

**0.4 Salvage Context Utilities**

* From:

  * `context.py`
  * `file_context.py`
  * `text_analysis.py`
  * `token_utils.py`
* Integrate into new memory system ONLY where engine-agnostic.

**0.5 Salvage Tool Runtime Utilities**

* From:

  * `filesystem.py`
  * `json_io.py`
  * `execution.py`
  * `plan_validation.py`
* Use only for deterministic tool runtime; remove executor assumptions.

**0.6 Quarantine Everything Else**

* Everything not explicitly listed above stays in `legacy/king_arthur/`
* Nothing else imported into engine.

---

# ✅ **Phase 1 — Project Skeleton & Module Layout (Core Engine Only) COMPLETE**

**Goal:** Generate the directory structure for a clean Agent Engine aligned with the overview.

```
agent_engine/
├── config/
│   ├── manifest_loader.py
│   ├── schema_registry.py
│   └── config_loader.py
├── core/
│   ├── errors.py
│   ├── types.py
│   ├── events.py
│   └── utils.py
├── json_engine/
├── memory/
├── workflow/
├── runtime/
│   ├── agent_runtime/
│   ├── tool_runtime/
│   ├── routing/
│   ├── overrides/
│   └── llm_adapter/
├── telemetry/
│   ├── event_bus.py
│   ├── event_types.py
│   └── sinks/
└── plugins/
```

This stage: skeleton + module stubs only.

---

# ✅ **Phase 2 — Config Loader, Schema Validation & Manifest System** COMPLETE

**Goal:** Create the foundation for all configuration-driven behavior.

### 2.1 Schema Registry

* JSON Schemas for:

  * Agents
  * Tools
  * Workflows (DAG nodes/edges)
  * Context Profiles
  * Plugins/hooks
  * Overrides
  * Memory tiers
* Validation engine using salvaged utilities.

### 2.2 Manifest Loader

* Loads YAML/JSON manifests
* Converts everything to JSON internally
* Validates against schema registry
* Provides canonical Python objects

### 2.3 Cross-Manifest Integrity Checks

* Workflow DAG validation
* Tool capability checks
* Agent/tool/pipeline referencing rules

### 2.4 Task Persistence & Resumability ✅

Tasks must be reconstructible from persisted state:

* **Task Serialization:** ✅ `to_dict()` / `from_dict()` methods on Task
* **State Checkpointing:** ✅ Store task state at stage boundaries
* **Resume Logic:** ✅ Ability to resume from last completed stage
* **Integration with ProjectMemory:** ✅ Store task history for later retrieval

Implemented:
* ✅ `TaskManager.save_checkpoint(task_id)` - Serialize current state
* ✅ `TaskManager.load_checkpoint(task_id)` - Restore task from checkpoint
* ✅ `TaskManager.list_tasks(project_id)` - Query task history
* ✅ `TaskManager.get_task_metadata(task_id)` - Lightweight metadata inspection

Storage backend: JSON files in `.agent_engine/tasks/{project_id}/{task_id}.json`

---
# 🔀 **Phase 3 — Workflow Graph & Pipeline Executor**

**Goal:** Implement the DAG-based workflow engine as described in the overview.

### 3.0 Router & Pipeline Selection

The Router is a first-class component that selects which pipeline template to
run for a Task, assigns agents (primary + backups), and resolves conditional
edges at runtime. The Pipeline Executor uses the Router to drive high-level
routing decisions; Decision stages produce structured decision artifacts that
the Router evaluates against outgoing edge conditions.

Router responsibilities:
- `select_pipeline(task_spec) -> pipeline_id` — pick pipeline template
- `assign_agents(pipeline, task) -> mapping[node_id] = agent_variant` — choose agent variants
- `resolve_edge(task, node, decision_output) -> edge_id` — deterministically pick next edge
- emit routing events and append a routing trace to the Task record

Router constraints:
- Must be manifest-driven and pluggable
- Must record its decisions (trace) on the Task for debugging and telemetry
- Must consult `FailureSignature` fallback matrix when errors occur

Note: Decision stage outputs MUST be typed JSON that reference condition keys or normalized edge names; the Router performs safe evaluation only against declared condition expressions (see `Edge Condition Schema` below).

### 3.1 Graph Representation

The workflow graph has two independent design axes:

**A. Stage Types** (what the node *does*):
* **Agent Stage** - Executes an LLM agent with prompt + context
* **Tool Stage** - Executes a deterministic tool or external call
* **Start Stage** - Entry point(s) for pipeline execution
* **End Stage** - Terminal node(s) marking completion

**B. Graph Roles** (how the node behaves in the DAG):
* **Transformation Node** - Single input → single output (most stages)
* **Decision Node** - Single input → multiple outputs (routing/branching)
* **Merge Node** - Multiple inputs → single output (join point)

A stage's *type* determines its execution logic.
A stage's *role* determines its connectivity in the DAG.

**Example:** An "agent stage" with "decision node" role calls an LLM and routes based on output.

* Edge types: normal / error / fallback / policy-driven

### 3.2 DAG Validator

* Static checks for:

  * No cycles
  * All nodes reachable
  * Allowed transitions based on type
  * Schema-conforming

The validator runs at manifest/load time and raises clear validation errors for invalid graphs.

### 3.3 Pipeline Executor

* Stage execution loop
* Node input/output contract
* Routing hooks
* Telemetry emission

This produces the core execution model of Agent Engine.

Executor operational rules:
- At the start and end of each stage the executor MUST call `TaskManager.save_checkpoint(task_id)` so tasks are resumable from the last completed stage.
- Before executing a stage the executor MUST emit a `stage_started` event; on completion emit `stage_finished` with full telemetry payload (see Telemetry fields below).
- On Decision stages the executor must persist the decision artifact and call `Router.resolve_edge()` to determine the outgoing edge.
- On runtime exceptions the executor must map the exception to a `FailureSignature`, consult the fallback matrix, and follow any configured error/fallback edges automatically.
- The executor must support configurable concurrency for branch execution and respect merge policies when joining branches.

### 3.4 Stage Function Library

Each stage type requires a defined execution pipeline. Implement:

**Agent Stage Pipeline (recommended lifecycle):**
1. Prepare input: assemble context (from ContextAssembler via `build_context(task, node, profile)`) and apply HEAD/TAIL + compression as required
2. Emit `stage_started` event (telemetry start)
3. Build prompt (system + user + context)
4. Call LLM (via LLM Adapter)
5. Validate JSON output (via JSON Engine); apply repair strategies or mark failure
6. Store result into Task record
7. Call `TaskManager.save_checkpoint()`
8. Emit `stage_finished` event (telemetry end)

Notes:
- The executor also emits `agent_call`/`agent_response` events inside this sequence with token usage and model metadata.

Plugin hook points (must be available to plugins):
- `before_task` / `after_task`
- `before_stage` / `after_stage`
- `before_agent_call` / `after_agent_call`
- `before_tool_call` / `after_tool_call`
- `on_stage_error`

Telemetry requirements (Agent & Tool stages):
- `event_type` (e.g., `agent_call`, `tool_call`, `stage_started`, `stage_finished`)
- `timestamp` (ISO8601)
- `task_id`
- `node_id`
- `stage_name`
- `latency_ms`
- `model` (for agent calls)
- `token_usage` (`prompt_tokens`, `completion_tokens`, `total_tokens`)
- `cost_usd` (optional)
- `success` (bool)
- `failure_signature` (if error)
- `context_fingerprint` (hash/summary of context used)
- `compression_ratio` (if any compression applied)

Context paging telemetry MUST record which sources were included (task_store, project_store, global_store) and any summaries used.

**Tool Stage Pipeline:**
1. Prepare input: validate inputs (against tool schema) and apply permissions
2. Emit `stage_started` event
3. Execute tool (handler dispatch)
4. Validate outputs (against tool schema)
5. Store result into Task record
6. Call `TaskManager.save_checkpoint()`
7. Emit `stage_finished` event

Tool notes:
- For `ToolPlan`-driven execution see `3.7 ToolPlan Execution & Rollback`.

**Decision Stage Pipeline:**
1. Prepare input (include decision-specific context)
2. Emit `stage_started`
3. Evaluate decision logic (from stage config or agent output)
4. Persist decision artifact on Task
5. Call `Router.resolve_edge(task, node, decision_output)`
6. Call `TaskManager.save_checkpoint()`
7. Emit `stage_finished`

**Merge Stage Pipeline:**
1. Wait for incoming branch results per merge policy
2. Aggregate inputs (as configured)
3. Store aggregated result and checkpoint
4. Emit `stage_finished`

Create `stage_library.py` with functions for each pipeline.
Map stage type → pipeline function in Pipeline Executor.

### 3.5 Context Assembly

Context Assembly is a mandatory pre-stage operation for Agent stages. The ContextAssembler must be manifest-driven and follow `ContextProfile`s declared in manifests.

Requirements:
- `ContextProfile` fields: `name`, `max_tokens`, `retrieval_policy`, `sources` (task_store, project_store, global_store), `compression_mode` (CHEAP|BALANCED|MAX_QUALITY).
- HEAD/TAIL policy: always include system wrapper and the most recent N turns (TAIL). Compress or summarize middle history when token budgets are tight.
- `ContextRequest` produced by `ContextPolicy(task_spec, mode, agent_profile)` must include: `domains`, `files`, `history_types`, and `token_budget`.
- The ContextAssembler must log a `context_paging` telemetry object for each agent call containing: `included_sources`, `items_count`, `total_tokens`, `compression_ratio`, `fingerprint`.

Implementation notes:
- The ContextAssembler should expose a `build_context(task, node, profile) -> ContextPackage` function used by Agent Stage pipelines.
- Compression/summarization may be delegated to an assistant adapter but must be recorded in telemetry and reversible for debugging (store summaries alongside originals in the Task record).

### 3.6 Edge Condition Schema (brief)

Edges that include conditions MUST express them as a manifest-declared structured condition, not arbitrary code. A simple example schema:

```
{ "condition_type": "match_key", "key": "decision.outcome", "op": "eq", "value": "approved" }
```

The engine will provide a safe evaluator that can compare scalar values, check membership in lists, and evaluate numeric ranges. Agent-driven decisions must return a JSON object with explicit keys referenced by edge conditions.

### 3.7 ToolPlan Execution & Rollback

Tool execution for agent-driven workflows must follow a deterministic `ToolPlan` contract.

`ToolPlan` schema (summary):
```
{ "steps": [ { "id": "s1", "tool_id": "write_file", "inputs": {...}, "reason": "apply patch", "kind": "workspace_mutation" } ] }
```

Executor behavior:
- When an Agent Stage returns a `ToolPlan`, the Pipeline Executor must validate the `ToolPlan` against declared tool schemas before execution.
- Execute each step sequentially (or as configured), saving a checkpoint after each step via `TaskManager.save_checkpoint()`.
- Log every tool call as telemetry (tool_id, inputs (redacted per policy), result summary, latency_ms, success).
- For `workspace_mutation` steps, the engine must support rollback hooks. Tools that mutate state must declare compensating actions or allow snapshot/restore semantics. The executor must attempt rollback on catastrophic failure and record rollback outcome in telemetry.

Security & safety:
- Tools without explicit `workspace_mutation` capability must not alter persistent state.
- The executor must enforce per-tool permission constraints from manifests before invocation.

### 3.8 Failure Signatures & Fallback Matrix

All failures in the pipeline must map to a `FailureSignature` and be recorded in telemetry. Example `FailureSignature` fields:
- `code` (e.g., `json_parse_error`, `tool_crash`, `permission_denied`, `timeout`)
- `stage_id`
- `severity` (`info`|`warning`|`error`|`critical`)
- `short_tag` (machine-friendly tag)
- `message`

Fallback matrix:
- A manifest-configurable matrix maps `FailureSignature.short_tag` → action. Actions include: `retry_same_agent`, `switch_agent_variant`, `follow_error_edge`, `escalate_to_human`, `abort`.
- The Router/Executor consults the matrix when a stage fails. The chosen action is executed (e.g., retry with backoff), and the outcome is appended to the Task routing trace and telemetry.

Post-mortem:
- For `critical` failures, create a compact post-mortem artifact attached to the Task containing the plan, tool logs, failure signature, and suggested remediation tags.

### 3.9 Concurrency & Merge Policies

Execution model:
- The Pipeline Executor should support two execution modes configurable per pipeline: `synchronous` (single-threaded step-by-step) and `concurrent` (parallel branch execution with join rules).

Merge policies (configurable on Merge nodes):
- `wait_for_all` — wait for all incoming branches to complete
- `quorum` — require N of M branches succeed (specify `min_successes`)
- `first_success` — proceed on first successful branch; cancel remaining

Failure handling in branches:
- If a branch fails under `wait_for_all`, the merge policy may: include failure as input, follow an error-edge, or consult fallback matrix.
- Branch cancellation must be cooperative; executor should attempt to stop running work and record cancellation telemetry.

Resource & locking considerations:
- Document that concurrent execution may require locking for shared resources (files, DB rows). Tools should be designed to be idempotent where possible.

### 3.10 Expanded Testing & Examples (details)

Tests for Phase 3 must be automated and include:
- Unit tests for DAG validator and safe condition evaluator
- Integration tests for Pipeline Executor with mocked LLM adapter and mocked tools verifying: routing decisions, `TaskManager` checkpoints, telemetry emitted, and fallback actions
- Concurrency tests for the executor covering merge policies and branch cancellations
- E2E example test using `configs/basic_llm_agent` that runs a representative DAG with deterministic mock adapters and asserts final Task state and telemetry presence

Provide simple mock adapters in `tests/mocks/`:
- `mock_llm_adapter` — returns deterministic JSON responses
- `mock_tool_adapter` — deterministic tool results, configurable to fail for testing fallback

---

# 🧠 **Phase 4 — Agent Runtime (LLM Adapter, Prompt Builder, Replies)**

**Goal:** Implement generic agent behavior, NOT pattern-specific logic.

### 4.1 LLM Adapter Interface

Backend-agnostic LLM interface with full observability:

**Required Methods:**
```python
class LLMClient(Protocol):
    def complete(
        self,
        messages: List[dict],
        model: str,
        max_tokens: int,
        temperature: float,
        response_schema: Optional[dict] = None,
        timeout: Optional[float] = None
    ) -> LLMResponse
```

**LLMResponse Structure:**
```python
@dataclass
class LLMResponse:
    content: str  # or dict if JSON mode
    model: str
    finish_reason: str
    usage: TokenUsage
    latency_ms: float
    cost_usd: Optional[float]
```

**TokenUsage Tracking:**
```python
@dataclass
class TokenUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
```

**Implementations Required:**
* OpenAI adapter (GPT-4, GPT-3.5)
* Anthropic adapter (Claude Opus, Sonnet, Haiku)
* Local model adapter (Ollama, LM Studio)

**Features:**
* Automatic cost calculation (model-specific pricing table)
* Timeout handling with graceful degradation
* Retry logic (3 attempts with exponential backoff)
* Streaming support (optional, for future)
* Request/response logging for debugging

### 4.2 Prompt Construction

* Deterministic prompt builder
* JSON schema for agent output
* No “magic” patterns (ReAct etc.)

### 4.3 JSON Response Enforcement

Integrate salvaged JSON Engine with comprehensive error handling:

**EngineError Hierarchy:**
* Base class: `EngineError(code, message, context, recovery_suggestion)`
* Error codes: `validation`, `routing`, `tool`, `agent`, `json`, `security`, `unknown`
* Severity levels: `info`, `warning`, `error`, `critical`

**Schema Registry Integration:**
* All manifests validated against registered schemas
* Runtime JSON validated against output schemas
* Schema version compatibility checking

**Repair Strategies:**
* Syntax repair (fix trailing commas, missing braces)
* Schema repair (add missing required fields with defaults)
* Re-ask with error context (when repair impossible)

**Retry Logic:**
* Retry count: configurable per stage (default 3)
* Exponential backoff between retries
* Include previous error in retry context
* Escalate to error handler after max retries

Implement in `json_engine.py`:
* `validate(data, schema_id)` → (is_valid, error)
* `repair_and_validate(data, schema_id)` → (repaired_data, error)
* `EngineError` class hierarchy

---

# 🧰 **Phase 5 — Tool Runtime (Deterministic, Safe, Configurable)**

**Goal:** Implement tool execution as a pure deterministic runtime.

### 5.1 Tool Interface

* Input/Output contract
* Schema validation
* Manifest-defined capabilities

### 5.2 Execution Sandbox

* os/fs/network permissions
* analysis_only mode
* dry_run mode
* timeouts
* execution logs

### 5.3 Security Model

Comprehensive security framework for tool execution:

**1. Tool Permission Levels:**
* `READ_ONLY` - File reads, queries, analysis
* `WORKSPACE_MUTATION` - File writes/edits within workspace
* `EXTERNAL_NETWORK` - HTTP requests, API calls
* `SYSTEM_COMMANDS` - Shell/bash execution
* `HARDWARE_ACCESS` - GPU, special devices

**2. Workspace Boundaries:**
* Define workspace root at engine initialization
* All file operations validated against workspace root
* Path traversal attacks blocked (use `filesystem_safety.py`)
* Symlink escapes prevented

**3. Execution Modes:**
* `analysis_only` - No mutations, read-only access
* `dry_run` - Simulate mutations, don't execute
* `normal` - Full execution with permission checks
* `review_required` - Human approval for high-risk operations

**4. Command Restrictions:**
* Dangerous command patterns blocked (rm -rf, sudo, mkfs)
* Whitelist of safe commands in analysis_only mode
* Network access gated by tool capabilities

**5. Implementation:**
Create `security.py` with:
* `check_tool_permissions(tool: ToolDefinition, mode: ExecutionMode)` → SecurityDecision
* `validate_workspace_path(path: str)` → bool
* `check_command_safety(command: str)` → SecurityDecision
* `enforce_execution_mode(mode: ExecutionMode, tool: ToolDefinition)` → bool

### 5.4 Tool Hooks

* before_tool_call
* after_tool_call
* on_tool_error

*No app-specific tools included—users provide them.*

---

# 🧩 **Phase 6 — Memory & Context System**

**Goal:** Implement the multi-tier memory system from the overview.

### 6.1 Memory Tiers

* TaskMemory
* ProjectMemory
* GlobalMemory

### 6.2 ContextAssembler

* Collates:

  * memory
  * retrieval policies
  * profile selection
  * token budgeting
* Uses salvaged text/context utilities where appropriate

### 6.3 Retrieval Policies

Implement concrete retrieval strategies:

**Recency Policy:**
* Select most recent N items
* Weight by timestamp (exponential decay)

**Hybrid Scoring Policy:**
* Combine recency (40%) + relevance (40%) + importance (20%)
* Relevance: keyword matching or embedding similarity
* Importance: user-tagged or inferred priority

**Token Budgeting:**
* Allocate token budget across tiers (task 40%, project 40%, global 20%)
* Crop to budget using HEAD/TAIL preservation
* Compress middle content if compression policy enabled

**Profile-Based Retrieval:**
* Different profiles for different agent types (e.g., coder vs analyst)
* Configurable via ContextProfile schema

Create `retrieval_policies.py` with:
* `RecencyPolicy` class
* `HybridScoringPolicy` class
* `TokenBudgetEnforcer` class
* Policy interface for extensibility

---

# 🧭 **Phase 7 — Router & Routing Policies**

**Goal:** Implement routing at the engine level, not app level.

### 7.1 Router Core

* Takes workflow graph + task state
* Determines next node
* Handles fallbacks, error branches

### 7.2 Routing Policies

* Rule-based
* Manifest-driven
* No RL/evolution at core

### 7.3 Override Surface

* Integrates optional override subsystem
* Must remain entirely configuration-driven

---

# 📡 **Phase 8 — Telemetry & Event Bus**

**Goal:** Provide a flexible telemetry/event system used by plugins.

### 8.1 Event Bus

* Async or sync dispatch
* Multiple sinks (file, stdout, HTTP, plugin)

### 8.2 Event Types

* agent_call_started
* agent_call_finished
* tool_call_started
* tool_call_finished
* workflow_transition
* error
* system_stats

### 8.3 Telemetry Integration

* Time
* Token usage
* Costs
* Error/fallback events

No analytics baked in—only raw events + sinks.

---

# 🔌 **Phase 9 — Plugin & Hook System**

**Goal:** Create the extension layer future features depend on.

### 9.1 Hook Interface Definition

Define the complete hook API:

**Hook Signatures:**
```python
# Task-level hooks
def before_task(task: Task, config: EngineConfig) -> Optional[Task]
def after_task(task: Task, result: Any) -> None
def on_task_error(task: Task, error: EngineError) -> Optional[Task]

# Stage-level hooks
def before_stage(task: Task, stage: Stage, context: ContextPackage) -> Optional[Tuple[Stage, ContextPackage]]
def after_stage(task: Task, stage: Stage, output: Any) -> None
def on_stage_error(task: Task, stage: Stage, error: EngineError) -> Optional[str]  # Returns next_stage_id or None

# Agent-level hooks
def before_agent(task: Task, stage: Stage, prompt: dict) -> Optional[dict]
def after_agent(task: Task, stage: Stage, response: dict) -> Optional[dict]

# Tool-level hooks
def before_tool(task: Task, tool_id: str, inputs: dict) -> Optional[dict]
def after_tool(task: Task, tool_id: str, output: Any) -> None
```

**Hook Constraints:**
* All hooks are **synchronous** (no async)
* Hooks are **fail-open** by default (exceptions logged, execution continues)
* Hooks can modify data by returning non-None values
* Hook execution order: registration order

**Hook Call Order:**
1. before_task → 2. before_stage → 3. before_agent/before_tool → 4. execution → 5. after_agent/after_tool → 6. after_stage → 7. after_task

Create `hooks.py` with hook interface definitions and dispatcher.

### 9.2 Plugin Loader

* Manifest-defined
* Optional
* Hot-reloadable (later)

### 9.3 Built-In Minimal Plugins

* Logging plugin
* Simple telemetry sink

---

# 🎛 **Phase 10 — Patterns Library (Optional, App-Layer)**

**Goal:** Provide optional templates—not core engine behavior.

**Note:** These patterns are **optional** and **not** part of core engine. The engine must function without them.

### 10.1 Agent Templates

* implementer
* analyst
* strategist
* assistant
* etc.

### 10.2 Workflows

* simple linear
* analysis → implement → review
* committee pattern
* supervisor pattern

### 10.3 These must be optional.

The engine must not depend on any of them.

---

# 🔍 **Phase 11 — Advanced Application-Layer Plugins (Optional)**

**IMPORTANT:** These are **NOT core engine components**. They are application-layer plugins that consume the engine's APIs. The engine must NOT depend on any of these.

This is where the "awesome later" features belong.

### 11.1 ReAct Pattern Plugin

### 11.2 Post-Mortem Analyst Plugin

### 11.3 Challenger Evolution Plugin

### 11.4 Carbon/Cost-Aware Routing Plugin

These are **not** core.

They consume telemetry and augment routing through hooks.

---

# 🧪 **Phase 12 — Test Suite & Production Hardening**

### 12.1 Unit Tests

### 12.2 Integration Tests

### 12.3 Manifest Validation Tests

### 12.4 Workflow Graph Tests

### 12.5 Memory/Routing/Agent/Tool Runtime Tests

### 12.6 Benchmarking Environment

* Latency
* Throughput
* Token cost
* Memory usage

### 12.7 Documentation

* Developer guide
* Manifest reference
* Extension guide
* Plugin/hook guide
* Patterns catalog

---

# 🎉 **End Result**

A **production-ready, modular Agent Engine**, fully aligned with AGENT_ENGINE_OVERVIEW.md:

* Manifest-driven
* Reliable JSON engine
* DAG workflows
* Deterministic tool runtime
* Generic agent runtime
* Retrieval-aware memory system
* Routing with fallback
* Comprehensive telemetry
* Plugin extensibility
* Optional patterns
* Optional advanced modules
