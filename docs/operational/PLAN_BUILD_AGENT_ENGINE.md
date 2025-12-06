## PLAN_BUILD_AGENT_ENGINE v2

*(Aligned with AGENT_ENGINE_OVERVIEW, AGENT_ENGINE_SPEC, RESEARCH, and current repo state)*

### Assumptions

* Canonical behavior is defined by **AGENT_ENGINE_OVERVIEW.md**, **AGENT_ENGINE_SPEC.md**, and **RESEARCH.md**; any conflicts MUST resolve in favor of those docs.   
* Many core schemas and config loader are already solid; we **refine and wire**, not reboot the world. 

Each phase below is intended to be implementable via a **single Haiku / Copilot “Act Mode” prompt**. For each phase you’ll feed:

* This phase’s section
* The canonical docs
* The status report
* The relevant files listed under “Files to touch”

---

## Phase 0 – Repo Cleanup, Guardrails, and Public API Shell

**Goal:** Align the repo skeleton with the canonical docs, mark what’s “core engine vs extras”, and introduce a stable public façade without deeply changing behavior yet.

### Files to touch

* `src/agent_engine/__init__.py`
* `src/agent_engine/engine.py` **(new)**
* `src/agent_engine/config_loader.py`
* `docs/operational/README.md`
* (Read-only for context) `examples/basic_llm_agent/cli.py`, `configs/basic_llm_agent/*`

### Key implementations

1. **Engine façade skeleton**

   * Create `Engine` class in `engine.py` exposing the minimal top-level API (no complex logic yet, mostly delegating):

     * `Engine.from_config_dir(config_dir: str, llm_client: LLMClient, *, telemetry: Optional[TelemetryBus] = None, plugins: Optional[PluginManager] = None) -> Engine`
     * `Engine.create_task(input: str | TaskSpec, *, mode: str | TaskMode = "default") -> Task`
     * `Engine.run_task(task: Task) -> Task`
     * `Engine.run_one(input: str | TaskSpec, mode: str | TaskMode = "default") -> Task`
   * Internally wire:

     * `config_loader.load_engine_config()` 
     * `runtime.task_manager.TaskManager`
     * `runtime.router.Router`
     * `runtime.pipeline_executor.PipelineExecutor` (current implementation, no new behavior)

2. **Public API boundary**

   * Re-export in `__init__.py`:

     * `Engine`
     * reusable schemas (`Task`, `AgentDefinition`, `ToolDefinition`, `WorkflowGraph`, `Pipeline`, etc.) as **types** only, not convenience constructors. 
   * Document in docstring: “Example apps must **only** use the Engine API and public schemas; no imports from `runtime.*`.”

3. **Config and docs alignment**

   * Update `docs/operational/README.md` to describe:

     * How to instantiate `Engine` from a config directory.
     * Explicitly call out that `examples/*` are non-canonical and **must use only `Engine`**, not runtime internals.
   * Add a short section naming all config surfaces (agents, tools, workflow, pipelines, memory, plugins) and pointing to schemas. 

### Invariants & edge cases

* `Engine` must not internally hard-code any particular app behavior; everything must come from manifests and/or TaskSpec. 
* `Engine.run_one` must be safe even if called repeatedly in a long-lived process (no global state leaks).
* The new façade **must not break existing tests**; if needed, implement it as thin wrapper around existing pipeline executor.

### Minimum tests

* Add tests in `tests/test_runtime.py`:

  * `test_engine_from_config_dir_runs_basic_llm_agent` using `configs/basic_llm_agent` and verifying the same behavior as `test_basic_llm_agent_example.py`.
* Add tests in `tests/test_imports.py`:

  * Ensure `from agent_engine import Engine` works and no internal modules leak unexpectedly.

---

## Phase 1 – Core Schemas, DAG Model, and Manifest System Finalization

**Goal:** Lock down the core data model (Task, Stage, Workflow, Node/Edge) and manifest validation such that later phases can safely rely on them.

Most of this exists and is salvageable; we are tightening behavior and documenting invariants. 

### Files to touch

* `src/agent_engine/schemas/`:

  * `task.py`, `stage.py`, `workflow.py`, `agent.py`, `tool.py`, `memory.py`, `event.py`, `override.py`, `tool_io.py`, `registry.py`
* `src/agent_engine/config_loader.py`
* `tests/test_schemas_models.py`
* `tests/test_dag_validator.py`
* `tests/test_config_loader_and_json_engine.py`

### Key implementations

1. **Explicit node / edge semantics**

   * Ensure `WorkflowGraph` and `Stage` schemas clearly encode:

     * Node roles: agent, tool, decision, merge, feedback, generic linear. Map to `StageType` enum values with names that match the plan/spec. 
     * Edge types: normal, error, conditional, fallback (if present).
   * Add comments & docstrings clarifying:

     * A node can be both “agent node” and “decision node” logically; StageType covers **execution role**, while node wiring (edges) encodes decisions/merges.

2. **DAG validator completeness**

   * Confirm `workflow.py` DAG validator:

     * Validates no cycles, reachable entry/exit nodes, valid edge targets. 
     * Enforces that conditional edges originate only from decision stages.
     * Enforces that merge stages have multiple inbound edges and exactly one outbound edge (unless explicitly marked terminal).

3. **Manifest & schema registry**

   * Ensure `registry.py` registers JSON Schema for:

     * Agents, tools, workflows, pipelines, memory, plugins, overrides, events. 
   * In `config_loader.py`:

     * Ensure all manifests are validated against the registry and invalid manifests raise structured `EngineError` with `EngineErrorCode.CONFIG_ERROR` (or equivalent). 

4. **Override and event schemas**

   * Clarify `OverrideSpec`, `OverrideKind`, `Event`, `EventType` enums and add comments tying them to later runtime phases (router, context, telemetry). 

### Invariants & edge cases

* No manifest surface may bypass schema validation.
* DAGs with invalid edge types or illegal transitions must fail at config load time, not at runtime.
* Overrides must be representable entirely via schemas (no hidden magic fields).

### Minimum tests

* Extend `test_schemas_models.py`:

  * Round-trip (create → serialize → validate → deserialize) for all major schemas.
* Extend `test_dag_validator.py`:

  * Invalid DAG cases: cycles, unreachable terminal, decision node with non-conditional edges, merge with single inbound edge.

---

## Phase 2 – Pipeline Executor & Task Manager: Robust DAG Execution

**Goal:** Bring pipeline execution and task lifecycle up to spec: full DAG traversal, merge behavior, basic error paths, checkpoint resumption. 

### Files to touch

* `src/agent_engine/runtime/pipeline_executor.py`
* `src/agent_engine/runtime/task_manager.py`
* `src/agent_engine/schemas/errors.py`
* `tests/test_runtime.py`
* `tests/test_pipeline_dag_execution.py`
* `tests/test_task_store.py`

### Key implementations

1. **Executor behavior**

   * In `PipelineExecutor.run(task: Task) -> Task`:

     * Implement MERGE stages:

       * Aggregate inbound stage results (e.g., list of outputs or dict keyed by edge source).
       * Define a simple merge policy (configurable later via manifests).
     * Implement error path routing:

       * When a stage fails with `EngineError`, consult OnErrorPolicy or equivalent and follow error edges (if defined).
       * Respect max retries per stage before taking fallback edge or failing task.

2. **Checkpoint resumption**

   * Integrate `TaskManager.load_checkpoint()` with `PipelineExecutor`:

     * Add `resume_task(task_id: str)` helper that loads a task, resumes from last recorded stage, and continues. 
   * Ensure checkpoints are written at least:

     * After task creation
     * After each stage finishes

3. **Error model**

   * Ensure `EngineError` and `FailureSignature` carry:

     * Stage id, node type, pipeline id, error category (agent/tool/json/context/etc.).
   * Executor must attach failure signature to Task and to telemetry (telemetry integration is wired later but API should be ready). 

### Invariants & edge cases

* Executor must always respect DAG constraints; it must not “invent” edges.
* Task status transitions: `PENDING → RUNNING → (COMPLETED | FAILED | CANCELLED)` and must persist.
* Merge stages must not drop results silently; if a merge cannot be constructed, raise structured error.

### Minimum tests

* `test_pipeline_dag_execution.py`:

  * Multi-branch DAG with merge node; verify merged output present on Task.
  * Execution from checkpoint resumes at correct stage.
* `test_runtime.py`:

  * Failure in intermediate stage triggers error edge or fallback node.

---

## Phase 3 – JSON Engine v1.0: Validation, Repair, and Retries

**Goal:** Make the JSON engine match the spec and research: structured validation, tiered repair, retry strategies, clear error categories.  

### Files to touch

* `src/agent_engine/json_engine.py`
* `src/agent_engine/schemas/errors.py`
* `src/agent_engine/utils/json_io.py` (if needed)
* `tests/test_config_loader_and_json_engine.py`
* New tests: `tests/test_json_engine_repair.py`

### Key implementations

1. **Error categorization**

   * Define JSON error categories in `EngineErrorCode` or similar:

     * `JSON_SYNTAX_ERROR`
     * `JSON_SCHEMA_MINOR_MISMATCH`
     * `JSON_SCHEMA_MAJOR_MISMATCH`
   * `validate()` returns either structured data or raises `EngineError` with category.

2. **Repair & retry strategy**

   * `repair_and_validate(raw_output, schema)`:

     * Parse raw string → minimal syntax repair (existing behavior).
     * If syntax OK but schema fails:

       * Apply small, deterministic repairs (fill missing optional fields with defaults, simple type coercions where safe).
     * Return `(result, repair_metadata)` including error category, repair actions.
   * Add `attempt_with_retries(call_fn, schema, retry_policy)` helper:

     * Handles up to N retries with escalating strategy: syntax repair → schema repair → re-ask with explicit error message. 

3. **Telemetry hooks**

   * JSON engine should emit events (or at least prepare them) describing error category and chosen strategy (telemetry wiring later).

### Invariants & edge cases

* No “creative” repair: only apply deterministic, schema-based changes.
* Catastrophic mismatches (empty/garbage output) must bubble up as errors; do not silently mask them.

### Minimum tests

* New `test_json_engine_repair.py`:

  * Syntax-only errors repaired successfully.
  * Minor schema mismatch (missing optional field) repaired.
  * Major mismatch triggers escalation (e.g., re-ask simulated via stub).

---

## Phase 4 – Agent Runtime v1.0: Structured Prompts, JSON Enforcement, Token Budgeting

**Goal:** Implement a real Agent Runtime that respects spec + research: deterministic prompt building, context assembly, JSON enforcement, basic token budgeting.  

### Files to touch

* `src/agent_engine/runtime/agent_runtime.py`
* `src/agent_engine/runtime/context.py`
* `src/agent_engine/utils/prompt_builders.py`
* `src/agent_engine/runtime/llm_client.py` (small adjustments for metadata)
* `src/agent_engine/json_engine.py` (integration)
* `tests/test_agent_and_tool_runtime.py`
* `tests/test_context_integration.py`
* `tests/test_llm_client.py`

### Key implementations

1. **Structured prompt builder**

   * Implement `build_agent_prompt(task, stage, context_package, agent_def)`:

     * System wrapper (HEAD)
     * Summary of task and key decisions so far
     * Relevant memory/context items (via ContextAssembler)
     * Explicit instructions about JSON schema to produce
   * Use RESEARCH “HEAD/TAIL, compress middle” guidelines when building the prompt. 

2. **AgentRuntime.run_agent_stage()**

   * Steps:

     * Call `ContextAssembler.build_context()` to get `ContextPackage`.
     * Build prompt via new prompt builder.
     * Call `LLMClient.generate()` with metadata including token budget.
     * Pass raw output through JSON engine `attempt_with_retries(...)`.
     * Attach JSON result to Task stage output; record token counts, latency.

3. **Token budgeting**

   * Use `utils/token_utils.py` to estimate token counts; enforce:

     * Configurable per-stage budget (from manifests) with simple enforcement:

       * If context > budget, call ContextAssembler with updated request to compress. 

### Invariants & edge cases

* Agent runtime must **not** invent tools or stages; all behavior must come from manifests and schemas.
* JSON engine failures must surface as structured errors, not raw tracebacks.

### Minimum tests

* `test_agent_and_tool_runtime.py`:

  * Agent stage produces valid JSON according to schema under normal conditions.
  * JSON syntax error triggers retry and is eventually repaired or escalated.
* `test_context_integration.py`:

  * When context is too large, compression is applied and HEAD/TAIL preserved.

---

## Phase 5 – Tool Runtime v1.0: ToolPlan Execution, Sandbox Integration, Workspace Safety

**Goal:** Implement Tool Runtime as per spec: ToolPlan parsing, deterministic tool execution, workspace boundaries, integration with security & telemetry.  

### Files to touch

* `src/agent_engine/runtime/tool_runtime.py`
* `src/agent_engine/runtime/task_manager.py` (recording tool outputs)
* `src/agent_engine/security.py`
* `src/agent_engine/utils/filesystem_safety.py`
* `src/agent_engine/schemas/tool_io.py`, `tool.py`, `memory.py` (if needed)
* `tests/test_agent_and_tool_runtime.py`
* `tests/test_plugins_and_patterns.py` (minimal adjustments)
* `tests/utils/test_filesystem_safety.py`

### Key implementations

1. **ToolPlan parsing & execution**

   * In `run_tool_stage(task, stage, tool_def, tool_plan: ToolPlan)`:

     * Validate `ToolPlan` structure against schema.
     * Execute steps sequentially (or clearly reject unsupported multi-step features for now).
     * Capture inputs/outputs and write into Task’s stage result (using `ExecutionInput` / `ExecutionOutput`). 

2. **Security integration**

   * Use `security.check_tool_call(tool_def, risk_level, requested_capabilities, task_safe_mode)`:

     * Enforce filesystem root restrictions using `filesystem_safety` helpers.
     * Gate network commands and shell execution per risk level and manifest-configured policies. 

3. **Workspace mutation tracking**

   * For tools that mutate workspace (e.g., file write):

     * Record summary of changes in Task (and optionally memory).
     * Add hooks for future rollback (even if rollback not fully implemented yet).

### Invariants & edge cases

* Tools may only execute if declared in manifests and allowed by security policies.
* Tool runtime must clearly differentiate between:

  * Tool failure (tool error)
  * Security rejection (permission denied)
  * Engine error (misconfiguration)

### Minimum tests

* `test_agent_and_tool_runtime.py`:

  * ToolPlan with simple read-only tool runs successfully and writes result.
  * Dangerous tool (e.g., outside root path) is blocked with clear error.
* `test_filesystem_safety.py`:

  * Additional tests covering path resolution and root enforcement.

---

## Phase 6 – Memory & Context System v1.0: File-Backed Stores, Context Profiles, Compression

**Goal:** Complete memory stores and context assembler according to overview + research: task/project/global stores, explicit context profiles, compression actually applied.  

### Files to touch

* `src/agent_engine/runtime/context.py`
* `src/agent_engine/runtime/memory/backend.py`
* `src/agent_engine/runtime/memory/task_store.py`
* `src/agent_engine/runtime/memory/project_store.py`
* `src/agent_engine/runtime/memory/global_store.py`
* `src/agent_engine/schemas/memory.py`
* `src/agent_engine/utils/file_context.py`, `token_utils.py` (if needed)
* `tests/test_memory_backend.py`
* `tests/test_task_store.py`, `test_project_store.py`, `test_global_store.py`
* `tests/test_context_integration.py`

### Key implementations

1. **File-backed stores**

   * Implement disk-backed versions for task/project/global stores:

     * Stable directory layout (e.g., under configurable `memory_root`).
     * Simple JSONL or per-task JSON files; reuse `json_io` for robustness. 

2. **Context profiles**

   * Extend `MemoryConfig` and/or Context schemas to define **context profiles**:

     * Fields like `max_tokens`, `include_task_history`, `include_project_docs`, `k_recent_messages`.
   * `ContextAssembler.build_context(request)` must:

     * Interpret the profile.
     * Choose memory items from task/project/global stores according to policy.
     * Apply **HEAD/TAIL** policy and explicit middle compression. 

3. **Compression applied**

   * Implement actual compression logic using existing metrics (`importance`, `token_cost` in `ContextItem`). 
   * Remove TODO path: ensure compressed representation is used in agent prompts.

### Invariants & edge cases

* Memory must be optional but deterministic; if no items match profile, context is still valid.
* File-backed stores must be robust to partial writes and process restarts (no crash loops on corrupt entries).

### Minimum tests

* `test_task_store`, `test_project_store`, `test_global_store`:

  * Verify persistence across process boundaries (simulate by re-instantiating stores).
* `test_context_integration`:

  * Context profile with tight token budget results in compressed middle but preserved HEAD/TAIL.

---

## Phase 7 – Router v1.0: Deterministic Routing, Fallback Matrix, Overrides

**Goal:** Implement router to spec with deterministic behavior, error/fallback routing, and override handling (but **without** advanced learned/MoA routing yet; that will be optional later).  

### Files to touch

* `src/agent_engine/runtime/router.py`
* `src/agent_engine/schemas/task.py` (RoutingDecision)
* `src/agent_engine/schemas/override.py`
* `src/agent_engine/schemas/errors.py` (FailureSignature)
* `src/agent_engine/runtime/pipeline_executor.py` (router integration)
* `tests/test_runtime.py`
* `tests/test_dag_validator.py` (for routing-related constraints)

### Key implementations

1. **Routing core**

   * `Router.choose_pipeline(task: Task, pipelines: list[Pipeline]) -> Pipeline`:

     * Deterministic selection based on task mode, tags, and possibly simple scores from manifests.
   * `Router.next_stage(task, workflow_graph, current_stage, last_result, failure_signature=None)`:

     * Normal progression via edges defined in graph.
     * Error/fallback edges consulted when `failure_signature` present.

2. **Fallback matrix**

   * Encode a simple fallback matrix in config (or derived from manifests) mapping:

     * `(failure_category, current_stage_type) → fallback_stage_id` (optional).
   * Router consults this when `pipeline_executor` passes an error categorized by JSON engine or runtime. 

3. **Override integration**

   * Before making routing decisions, check for `OverrideSpec` on Task (e.g., “analysis only”, “skip tools”).
   * Adjust routing accordingly (e.g., avoid tool-heavy pipelines, require review stages).

### Invariants & edge cases

* Router must always respect DAG; it may pick which edge, but never invent edges.
* Overrides must be applied deterministically and traceably (record decisions on Task).

### Minimum tests

* `test_runtime.py`:

  * When a stage fails, router picks configured fallback node.
  * Overrides change pipeline choice (e.g., analysis-only pipeline selected).

---

## Phase 8 – Telemetry & Event Bus v1.0: Sinks, Cost Tracking, Wiring

**Goal:** Turn the current in-memory telemetry stub into the observability backbone described in the overview/spec.  

### Files to touch

* `src/agent_engine/telemetry.py`
* `src/agent_engine/schemas/event.py`
* `src/agent_engine/runtime/agent_runtime.py`
* `src/agent_engine/runtime/tool_runtime.py`
* `src/agent_engine/runtime/pipeline_executor.py`
* `src/agent_engine/runtime/task_manager.py`
* `src/agent_engine/runtime/llm_client.py`
* `tests/test_llm_client.py`
* `tests/test_runtime.py`
* `tests/test_plugins_and_patterns.py` (if they depend on events)

### Key implementations

1. **TelemetryBus + sinks**

   * Implement `TelemetryBus` with:

     * In-memory store (existing)
     * File sink (JSONL)
     * Stdout sink
   * Events include:

     * Task created, stage started/finished, agent/tool called, memory retrieved, routing decision, errors, cost/time metrics. 

2. **Cost & token metrics**

   * Extend `LLMClient` responses to include `prompt_tokens`, `completion_tokens`, `total_tokens`, `cost_estimate`.
   * Emit telemetry events carrying these metrics for each agent/tool call. 

3. **Wiring from runtimes**

   * Agent runtime, tool runtime, pipeline executor, and task manager must all emit appropriate events through `TelemetryBus`.

### Invariants & edge cases

* Telemetry must not crash the engine; sink failures should degrade gracefully (e.g., log + continue).
* Sensitive payloads must be redacted or metadata-only, as per future privacy design.

### Minimum tests

* `test_runtime.py`:

  * Running a simple pipeline produces expected sequence of telemetry events.
* `test_llm_client.py`:

  * Cost and token metrics propagated correctly.

---

## Phase 9 – Plugin & Hook System v1.0

**Goal:** Implement hook surfaces and plugin manager so that external code can observe and modify behavior without changing core engine.  

### Files to touch

* `src/agent_engine/plugins/manager.py`
* `src/agent_engine/telemetry.py` (for event subscription)
* `src/agent_engine/runtime/pipeline_executor.py`
* `src/agent_engine/runtime/agent_runtime.py`
* `src/agent_engine/runtime/tool_runtime.py`
* `src/agent_engine/runtime/context.py` (optional hooks)
* `src/agent_engine/schemas/override.py` (if plugin-configurable)
* `tests/test_plugins_and_patterns.py`

### Key implementations

1. **Hook surfaces**

   * Define hook points:

     * before/after task
     * before/after stage
     * before/after agent
     * before/after tool
     * on error / on task completion
   * Represent hooks as simple callables with typed payloads (e.g., `HookContext` objects).

2. **PluginManager**

   * Load plugin definitions from manifest (via config loader).
   * Register plugins, subscribe them to hooks/events.
   * Provide simple APIs:

     * `manager.register(plugin)`
     * `manager.emit(hook_name, context)`

3. **Integration**

   * Pipeline executor and runtimes call plugin hooks at well-defined points; plugin failures must not crash engine by default.

### Invariants & edge cases

* Hooks must be clearly documented and stable; breaking them should be treated as a breaking change.
* Plugins must not be able to bypass core security invariants (e.g., they can veto a tool call but not silently execute arbitrary ones).

### Minimum tests

* `test_plugins_and_patterns.py`:

  * Simple plugin that logs hook invocations; verify hooks fire in correct order.
  * Plugin that vetoes a tool call results in tool not being executed.

---

## Phase 10 – LLM Adapter Layer v1.0: Multi-Provider, Streaming, Token/Cost Accounting

**Goal:** Complete the LLM adapter layer to match overview/spec: backend-agnostic interface, multiple providers, token/cost tracking, streaming support.  

### Files to touch

* `src/agent_engine/runtime/llm_client.py`
* `src/agent_engine/schemas/agent.py` (if backend configuration fields needed)
* `src/agent_engine/config_loader.py` (LLM config support)
* `tests/test_llm_client.py`
* `tests/test_basic_llm_agent_example.py`

### Key implementations

1. **Common interface**

   * Finalize `LLMClient` protocol:

     * `generate(prompt: Prompt, *, temperature: float, max_tokens: int, ...) -> LLMResult`
     * `stream_generate(...) -> Iterable[LLMChunk]`
   * `LLMResult` must include:

     * `text`, `raw`, `prompt_tokens`, `completion_tokens`, `total_tokens`, `cost_estimate`.

2. **Adapters**

   * Implement:

     * `AnthropicLLMClient` (existing, refined)
     * `OllamaLLMClient`
     * `OpenAILLMClient` (new)
   * Configuration from manifests (model names, API keys via env/config).

3. **Streaming integration (minimal)**

   * Implement streaming in adapters (even if not yet used by Agent Runtime) with a simple interface; ensure non-streaming paths still work.

### Invariants & edge cases

* LLM adapters must not throw provider-specific exceptions; they should map into `EngineError` categories.
* Token and cost calculations must be deterministic for a given provider/version.

### Minimum tests

* `test_llm_client.py`:

  * Mocked adapters for all providers.
  * Token and cost fields present and sane.
* `test_basic_llm_agent_example.py`:

  * Example can switch between providers by changing manifest/config.

---

## Phase 11 – Security Model v1.0: Permissions, Safe Modes, Audit Logging

**Goal:** Upgrade the partial security layer into a proper permissions system as per overview + research, wired through Tool Runtime and, where relevant, Agent Runtime.  

### Files to touch

* `src/agent_engine/security.py`
* `src/agent_engine/utils/filesystem_safety.py`
* `src/agent_engine/runtime/tool_runtime.py`
* `src/agent_engine/schemas/tool.py`, `agent.py`, `memory.py` (permissions & safe-mode fields)
* `src/agent_engine/telemetry.py`
* `tests/utils/test_filesystem_safety.py`
* `tests/test_agent_and_tool_runtime.py`
* `tests/test_runtime.py`

### Key implementations

1. **Permissions model**

   * Define security policies:

     * Filesystem scopes (root + allowed subpaths).
     * Network access flags.
     * Shell execution toggles.
   * Attach policies to:

     * Tool definitions.
     * Agent definitions (what tools they may call).

2. **Safe modes & overrides**

   * Support flags like `analysis_only`, `dry_run` via overrides and/or Task mode.
   * Ensure Tool Runtime enforces these safe modes (e.g., log-only vs actual write).

3. **Audit logging**

   * Emit telemetry events for:

     * Permission checks
     * Denials
     * Potentially sensitive tool calls

### Invariants & edge cases

* No tool may run outside its configured capability set or allowed filesystem/network scope.
* Denials must be explicit and auditable.

### Minimum tests

* `test_agent_and_tool_runtime.py`:

  * Tools blocked by safe-mode flags.
* `test_filesystem_safety.py`:

  * Paths outside allowed root are rejected.

---

## Phase 12 – Patterns Library (Optional) & Manifest Templates

**Goal:** Provide optional pattern manifests (committee, supervisor, etc.) that are **strictly separated** from the core engine and can be used as examples.  

**Mark this phase as OPTIONAL / Phase N+; not required for core completion.**

### Files to touch

* `src/agent_engine/patterns/committee.py`, `supervisor.py`
* `configs/patterns/*` (new example manifests)
* `tests/test_plugins_and_patterns.py`

### Key implementations

* Implement simple helper functions or templates for:

  * Committee-of-agents pattern
  * Supervisor + worker pattern
* Ensure:

  * These rely only on public Engine APIs + manifests.
  * They are not required by any tests for the core engine (only by pattern-specific tests).

---

## Phase 13 – Example App & Public API-Only Usage

**Goal:** Ensure there is at least one example app that uses only the public Engine façade and public config surfaces.

### Files to touch

* `examples/basic_llm_agent/cli.py`
* `configs/basic_llm_agent/*`
* `tests/test_basic_llm_agent_example.py`
* `docs/operational/README.md`

### Key implementations

* Refactor `cli.py` to:

  * Instantiate `Engine` via `Engine.from_config_dir`.
  * Use `Engine.run_one` or `Engine.create_task` + `Engine.run_task`.
* Keep example simple but fully manifest-driven.

### Invariants & edge cases

* Example must not import from `runtime.*` directly.
* Changing manifests should allow reconfiguring the workflow without code changes.

### Minimum tests

* `test_basic_llm_agent_example.py`:

  * Confirm example uses Engine façade and that end-to-end behavior still works.

---

## Phase 14 – Tests, Hardening, and Minimal Benchmarks

**Goal:** Close coverage gaps identified in the status report, add edge-case tests, and introduce minimal performance/robustness checks.  

### Files to touch

* `tests/*` (multiple)
* Optionally new `tests/test_performance_basic.py`
* `Makefile` / `pyproject.toml` (optional test targets)

### Key implementations

* Add tests for:

  * Error/retry paths in executor and JSON engine.
  * Context compression and paging decisions.
  * Plugin system & hooks under failure.
  * Checkpoint save/load of large tasks.
  * Multi-task concurrency (simple parallel runs).
* Add a minimal benchmark-like test:

  * Run a simple pipeline N times and assert time and memory are within reasonable bounds (no leaks).

### Invariants & edge cases

* All phases’ new behavior must be covered by at least basic tests; no critical subsystem left untested on failure paths.
* Keep performance tests lightweight enough for normal CI runs.

---

## Phase N+ (Optional Advanced Features from RESEARCH)

These are explicitly **optional** and should be clearly marked as experimental features that depend on future research:   

* **Learned / MoA routing** (Mixture-of-agents, learned routers).
* **Learned retrieval policies for context** (dense retrievers, bandits).
* **Agent evolution** (manifest mutation, fitness-based selection).
* **RL-style safety training for tool use.**
* **Advanced patterns (ReAct debate, PromptBreeder, etc.).**

These should each become their own later phases that **plug into** the already-complete engine via telemetry, plugins, and existing schemas, not by rewriting the core.
