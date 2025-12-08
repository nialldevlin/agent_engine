## PLAN_BUILD_AGENT_ENGINE v2.1

*(Aligned with AGENT_ENGINE_OVERVIEW, AGENT_ENGINE_SPEC, RESEARCH, and current repo state)*

### Assumptions

* Canonical behavior is defined by **AGENT_ENGINE_OVERVIEW.md**, **AGENT_ENGINE_SPEC.md**, and **RESEARCH.md**; any conflicts MUST resolve in favor of those docs.
* Many core schemas and config loader are already solid; we **refine and wire**, not reboot the world.

Each phase below is intended to be implementable via a **single Haiku / Copilot "Act Mode" prompt** (subject to implementation status below). For each phase you'll feed:

* This phase's section
* The canonical docs
* The status report
* The relevant files listed under "Files to touch"

---

## Implementation Status Markers

Each phase is marked with one of three statuses:

* **🟢 HAIKU READY** – Implementation details are clear; Haiku can execute with these specs.
* **🔵 SONNET DESIGN** – Requires architectural/algorithmic design first; Sonnet designs, then Haiku implements.
* **🟡 NEEDS INFO** – Missing implementation details or dependencies; cannot proceed until clarified.

Phases are also grouped by implementation tier:
* **Core Engine Phases** (0-7, 10-11) – Must be complete for spec compliance.
* **Optional Phases** (12, N+) – Nice-to-have patterns and advanced features.

---

## Phase 0 – Repo Cleanup, Guardrails, and Public API Shell

**Goal:** Align the repo skeleton with the canonical docs, mark what’s “core engine vs extras”, and introduce a stable public façade without deeply changing behavior yet.

### Status (2025-12-05)

- ✅ `Engine` facade implemented with manifest validation, runtime wiring, tool handler registration, and public schema re-exports.
- ✅ README, plan, and tests (`tests/test_imports.py`, `tests/test_basic_llm_agent_example.py`, `tests/test_runtime.py`) now document/publicly verify that only the Engine façade is used.
- ✅ Tests: `pytest` (full suite) passes after the refactor.

The prior `examples/basic_llm_agent` CLI example has been removed because it no longer reflects the unfinished API backend. A future canonical example will be reintroduced once the runtime APIs stabilize.

### Files to touch

* `src/agent_engine/__init__.py`
* `src/agent_engine/engine.py` **(new)**
* `src/agent_engine/config_loader.py`
* `docs/operational/README.md`
* (Read-only for context) `examples/basic_llm_agent/cli.py`, `configs/basic_llm_agent/*`

### Key implementations

1. **Engine façade skeleton** ✅ complete

* Created `Engine` class in `engine.py` exposing the minimal top-level API (no complex logic yet, mostly delegating)

2. **Public API boundary** ✅ complete

* Re-export in `__init__.py`

3. **Config and docs alignment** ✅ complete

* Update `docs/operational/README.md` to how to use 'Engine' 

### Invariants & edge cases ✅ complete

* `Engine` must not internally hard-code any particular app behavior; everything must come from manifests and/or TaskSpec. 
* `Engine.run_one` must be safe even if called repeatedly in a long-lived process (no global state leaks).
* The new façade **must not break existing tests**; if needed, implement it as thin wrapper around existing pipeline executor.

### Minimum tests ✅ complete

* Add tests in `tests/test_imports.py` 

---

## Phase 1 – Core Schemas, DAG Model, and Manifest System Finalization

**Status: 🟢 HAIKU READY** (schemas largely exist; mechanical refinement & wiring)

**Goal:** Lock down the core data model (Task, Stage, Workflow, Node/Edge) and manifest validation such that later phases can safely rely on them.

Most of this exists and is salvageable; we are tightening behavior and documenting invariants. This phase is critical and must be completed before most other phases can proceed.

### References
* AGENT_ENGINE_OVERVIEW §5 (Workflow Graph & Pipelines)
* AGENT_ENGINE_SPEC §3.2 (Workflow & Pipeline Executor)
* RESEARCH.md (DAG semantics and validation rules)

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
   * Include safe-mode flags: `analysis_only`, `dry_run`, and any task-level overrides (per AGENT_ENGINE_SPEC §4.6 and RESEARCH Appendix A).

5. **ToolPlan schema** *(NEW – from canonical docs)*

   * Define `ToolPlan` structure for tool invocation requests from agents (OVERVIEW §8, SPEC §4.3).
   * Minimal schema skeleton: `{ tool_name: str, arguments: dict, result_field?: str }` (exact structure per RESEARCH.md).
   * Include `ExecutionInput` and `ExecutionOutput` for recording tool I/O in Tasks (Phase 5 will detail execution).

6. **Built-in tool catalog** *(NEW – from canonical docs)*

   * Document which tools are built-in vs. user-defined (per SPEC §4.3 examples: `filesystem.write_file`, `filesystem.read_file`, `filesystem.list`, `command.run`).
   * Ensure tool registry can load both built-in and custom tool definitions from manifests.

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

**Status: 🔵 SONNET DESIGN** (core execution logic; requires design before implementation)

**Goal:** Bring pipeline execution and task lifecycle up to spec: full DAG traversal, merge behavior, basic error paths, checkpoint resumption.

### References
* AGENT_ENGINE_OVERVIEW §5 (Workflow Graph & Pipelines)
* AGENT_ENGINE_SPEC §3.2 (Workflow & Pipeline Executor semantics)

### Design Gaps (Requires Sonnet Input)
* **Merge semantics**: What is "simple merge policy"? List? Dict keyed by edge source? Aggregation rules? (see RESEARCH for details)
* **Error recovery matrix**: Complete error taxonomy (JSON errors, tool errors, context errors, routing errors, permissions errors).
* **Fallback routing**: Precise fallback matrix structure and lookup logic.

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

**Status: 🟡 NEEDS INFO** (depends on Phase 2 error taxonomy design)

**Goal:** Make the JSON engine match the spec and research: structured validation, tiered repair, retry strategies, clear error categories.

### References
* AGENT_ENGINE_OVERVIEW §10 (JSON Engine)
* AGENT_ENGINE_SPEC §3.5 (JSON Engine completion criteria)
* RESEARCH.md §5.2, §7 (JSON validation & repair strategies)

### Design Gaps (Blocked by Phase 2)
* Complete error taxonomy across all runtime components (tool errors, context errors, routing errors beyond JSON-only).
* Once Phase 2 defines the full error space, Phase 3 refines JSON-specific errors.

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

**Status: 🔵 SONNET DESIGN** (core prompt/context logic; requires design before implementation)

**Goal:** Implement a real Agent Runtime that respects spec + research: deterministic prompt building, context assembly, JSON enforcement, basic token budgeting.

### References
* AGENT_ENGINE_OVERVIEW §7 (Agent Runtime), §9 (Memory & Context)
* AGENT_ENGINE_SPEC §3.3 (Runtime - Agent Runtime completion criteria)
* RESEARCH.md §5.1-5.3 (Agent Runtime and context assembly details)

### Design Gaps (Requires Sonnet Input)
* **Compression algorithm**: Exact HEAD/TAIL preservation strategy and importance scoring for middle compression (token-based? importance-scored?).
* **Context profile semantics**: How does a profile map to memory selection? Query structure? Ranking/scoring details?
* **Prompt structure**: Exact prompt template and ordering (system wrapper, task summary, context items, JSON schema instructions).
* **Token budgeting enforcement**: When context exceeds budget, compression algorithm and thresholds.

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

**Status: 🔵 SONNET DESIGN** (tool execution model & security decisions; requires design before implementation)

**Goal:** Implement Tool Runtime as per spec: ToolPlan parsing, deterministic tool execution, workspace boundaries, integration with security & telemetry.

### References
* AGENT_ENGINE_OVERVIEW §8 (Tool Runtime), §14 (Security & Permissions)
* AGENT_ENGINE_SPEC §3.3 (Runtime - Tool Runtime completion criteria), §4.3 (Example tools)
* RESEARCH.md §3.1-3.3 (Tool Runtime and security model details)

### Design Gaps (Requires Sonnet Input)
* **ToolPlan structure** (detailed schema): Exact JSON structure for tool invocation requests from agents (minimal schema in Phase 1; full spec needed).
* **Built-in tool implementations**: Define which tools are engine-provided (filesystem operations, command execution) vs. user-defined.
* **Tool execution model**: Sequential vs. parallel step execution, multi-step ToolPlan support, error recovery per step.
* **Security decision logic**: Filesystem root enforcement, network/shell gating per risk level and manifest policies.

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

**Status: 🔵 SONNET DESIGN** (retrieval policies & memory layer architecture; requires design before implementation)

**Goal:** Complete memory stores and context assembler according to overview + research: task/project/global stores, explicit context profiles, compression actually applied.

### References
* AGENT_ENGINE_OVERVIEW §9 (Memory & Context system, five memory layers)
* AGENT_ENGINE_SPEC §3.4 (Memory & Context completion criteria)
* RESEARCH.md §1-2 (Memory tiers and retrieval policies)

### Design Gaps (Requires Sonnet Input)
* **Memory layer mapping**: Canonical docs describe five layers (Conversation, RAG, Agent State, Profile, Tool/Environment); map to task/project/global stores (Phase 1 identified three; how do five map to three?).
* **RAG integration**: Vector database seeding, semantic retrieval, document ingestion pipeline (currently unspecified).
* **Agent state memory**: Persistent JSON blob schema and storage (distinct from conversation memory).
* **Retrieval policies**: Exact algorithm for "hybrid" and "recency" policies; importance scoring; token budgeting interaction.
* **Context profile application**: How profiles (max_tokens, retrieval_policy, sources) translate to actual memory queries.

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

**Status: 🔵 SONNET DESIGN** (routing algorithm & fallback matrix; requires design before implementation)

**Goal:** Implement router to spec with deterministic behavior, error/fallback routing, and override handling (but **without** advanced learned/MoA routing yet; that will be optional later).

### References
* AGENT_ENGINE_OVERVIEW §6 (Routing system)
* AGENT_ENGINE_SPEC §3.3 (Runtime - Router completion criteria), §4.4-4.7 (Example manifest usage)
* RESEARCH.md §4.1-4.2 (Routing determinism and fallback logic)

### Design Gaps (Requires Sonnet Input)
* **Pipeline selection algorithm**: How are "task mode, tags, and simple scores" evaluated for deterministic pipeline choice?
* **Fallback matrix structure**: Precise format and lookup logic for `(failure_category, current_stage_type) → fallback_stage_id` mapping.
* **Override application semantics**: How do safe-mode flags and task-level overrides deterministically alter routing decisions? Traceability on Task?
* **Edge selection logic**: When multiple edges are available (e.g., from decision nodes), how does router select which to follow?

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

**Status: 🟢 HAIKU READY** (mechanical wiring of event emission and sinks, once event types are defined)

**Goal:** Turn the current in-memory telemetry stub into the observability backbone described in the overview/spec.

### References
* AGENT_ENGINE_OVERVIEW §11 (Telemetry & Event Bus)
* AGENT_ENGINE_SPEC §3.6 (Telemetry & Events completion criteria)
* RESEARCH.md §6-7 (Event types and observability)

### Note on Cost Estimation
* Cost per model must be configured externally (cost tables per provider/model); engine does not compute costs itself, only tracks token counts for cost calculation by sinks.
* See Phase 10 for LLM adapter cost tracking integration.

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

**Status: 🟢 HAIKU READY** (mechanical plugin registration and event subscription wiring)

**Goal:** Implement hook surfaces and plugin manager so that external code can observe and modify behavior without changing core engine.

### References
* AGENT_ENGINE_OVERVIEW §12 (Plugin & Hook System)
* AGENT_ENGINE_SPEC §3.7 (Plugin System completion criteria)
* RESEARCH.md §3.2, §5 (Hook surfaces and plugin integration points)

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

**Status: 🟢 HAIKU READY** (once LLMClient interface finalized; mostly provider-specific implementations)

**Goal:** Complete the LLM adapter layer to match overview/spec: backend-agnostic interface, multiple providers, token/cost tracking, streaming support.

### References
* AGENT_ENGINE_OVERVIEW §13 (LLM Backend Interface)
* AGENT_ENGINE_SPEC §3.8 (LLM Adapter completion criteria)
* RESEARCH.md §3-5 (Provider-specific considerations)

### Additional Details (from Canonical Docs)
* **Streaming support**: Phase overview mentions "streaming (even if not yet used)"; implement streaming interface in adapters but agent runtime (Phase 4) uses non-streaming for now.
* **Cost estimation**: Cost tables should be externally configurable per provider/model; engine tracks `prompt_tokens`, `completion_tokens`, `total_tokens` and lets plugins compute cost via external tables.
* **Supported providers**: Anthropic, OpenAI, Ollama (per plan); other providers can be added later.

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

**Status: 🔵 SONNET DESIGN** (permissions model architecture; requires design before implementation)

**Goal:** Upgrade the partial security layer into a proper permissions system as per overview + research, wired through Tool Runtime and, where relevant, Agent Runtime.

### References
* AGENT_ENGINE_OVERVIEW §14 (Security & Permissions)
* AGENT_ENGINE_SPEC §3.3 (Runtime - security component), §4.3 (Example tool permissions)
* RESEARCH.md Appendix A (Permissions & Safe Modes)

### Design Gaps (Requires Sonnet Input)
* **Permission model granularity**: Filesystem (root + subpaths), network (allow/deny list), shell execution flags; default + per-agent + per-tool overrides.
* **Safe-mode enforcement**: How `analysis_only` and `dry_run` flags block mutation operations in tools.
* **Audit event schema**: What permission checks and denials are logged; sensitivity redaction policy.

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

**Status: 🟢 HAIKU READY** (template implementations once core engine APIs stable)

**Goal:** Provide optional pattern manifests (committee, supervisor, chat) that are **strictly separated** from the core engine and can be used as examples.

**Mark this phase as OPTIONAL / Phase N+; not required for core completion.**

### References
* AGENT_ENGINE_SPEC §3.9 (Patterns Library - optional but clean)
* AGENT_ENGINE_OVERVIEW §1 (Patterns library as optional manifest templates)

### Pattern Implementations (from Canonical Docs)
* **Committee-of-agents pattern**: Multiple agents voting or reaching consensus
* **Supervisor + worker pattern**: One coordinator agent, multiple specialist workers
* **Chat pattern**: Conversational agent with memory and turn-taking (NEW – from canonical docs)

All patterns must:
* Rely only on public `Engine` APIs + manifests
* Be implemented as helper functions / manifests, not built-in behavior
* Have no core engine imports or dependencies
* Be disabled unless explicitly authored in `plugins.yaml` or manifest

### Files to touch

* `src/agent_engine/patterns/committee.py`, `supervisor.py`, `chat.py` (NEW)
* `configs/patterns/*` (new example manifests)
* `tests/test_plugins_and_patterns.py`

### Key implementations

* Implement simple helper functions or templates for:

  * Committee-of-agents pattern
  * Supervisor + worker pattern
  * Chat pattern (conversational loop with memory)
* Ensure:

  * These rely only on public Engine APIs + manifests.
  * They are not required by any tests for the core engine (only by pattern-specific tests).

---

## Phase 13 – Example App & Public API-Only Usage

**Status: 🟢 HAIKU READY** (CLI glue code; manifests drive all behavior)

**Goal:** Ensure there is at least one example app that uses only the public Engine façade and public config surfaces. Example manifests demonstrate all major features.

### References
* AGENT_ENGINE_SPEC §4 (Example Project Structure & Manifests)
* AGENT_ENGINE_OVERVIEW §1, §2 (Engine responsibilities and configuration)

### Detailed Manifest Structure (from Canonical Docs)
The example should include the full manifest suite from SPEC §4:
* **agents.yaml**: Agent definitions with models, context profiles, tool lists, output schemas
* **tools.yaml**: Tool definitions with types, filesystem roots, command allowlists
* **workflow.yaml**: DAG nodes (agent, tool, decision, merge) and edges with conditions
* **pipelines.yaml**: Pipeline templates mapping node types to stage sequences
* **memory.yaml**: Task/project/global stores and context profile configurations
* **plugins.yaml**: Telemetry loggers and optional cost tracking plugins

Example should mirror the "Code Gremlin" spec but simplified (e.g., one agent instead of three).

### Files to touch

* `examples/basic_llm_agent/cli.py`
* `configs/basic_llm_agent/agents.yaml` (refined per spec)
* `configs/basic_llm_agent/tools.yaml` (refined per spec)
* `configs/basic_llm_agent/workflow.yaml`
* `configs/basic_llm_agent/pipelines.yaml`
* `configs/basic_llm_agent/memory.yaml`
* `configs/basic_llm_agent/plugins.yaml`
* `tests/test_basic_llm_agent_example.py`
* `docs/operational/README.md`

### Key implementations

* Refactor `cli.py` to:

  * Instantiate `Engine` via `Engine.from_config_dir("configs/basic_llm_agent")`.
  * Use `Engine.run_one` or `Engine.create_task` + `Engine.run_task`.
* Manifests should be complete, matching SPEC §4 example structure.

### Invariants & edge cases

* Example must not import from `runtime.*` directly.
* Changing manifests should allow reconfiguring the workflow without code changes.
* All manifests must validate against engine schemas.

### Minimum tests

* `test_basic_llm_agent_example.py`:

  * Confirm example uses Engine façade and that end-to-end behavior still works.
  * Verify all manifests validate and load correctly.
  * Simple execution: create task → run pipeline → verify output structure.

---

## Phase 14 – Tests, Hardening, and Minimal Benchmarks

**Status: 🟢 HAIKU READY** (test writing once behaviors are defined in prior phases)

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

---

## Implementation Summary by Tier

### 🟢 HAIKU READY – Immediate Execution (No Design Blocker)
| Phase | Title | Dependencies |
|-------|-------|--------------|
| 0 | Repo Cleanup & API Shell | ✅ Done |
| 1 | Core Schemas & DAG Model | ✅ Done (precondition for 2+) |
| 8 | Telemetry & Event Bus | Phase 2 error taxonomy |
| 9 | Plugin & Hook System | Phase 8 event types |
| 10 | LLM Adapter Layer | None |
| 12 | Patterns Library | Phases 2–11 (core engine stable) |
| 13 | Example App & Manifests | Phases 2–11 (core engine stable) |
| 14 | Tests & Hardening | All prior phases for behavior specs |

### 🔵 SONNET DESIGN – Requires Design Input Before Implementation
| Phase | Title | Key Design Decisions |
|-------|-------|---------------------|
| 2 | Pipeline Executor & Task Manager | Merge semantics, error recovery matrix, fallback routing |
| 4 | Agent Runtime v1.0 | Prompt structure, compression algorithm, context profile application |
| 5 | Tool Runtime v1.0 | ToolPlan schema (detailed), tool execution model, security decision logic |
| 6 | Memory & Context System | Five-layer memory mapping, RAG integration, retrieval policies |
| 7 | Router v1.0 | Pipeline selection algorithm, fallback matrix structure, override application |
| 11 | Security Model v1.0 | Permission granularity, safe-mode enforcement, audit schema |

### 🟡 NEEDS INFO – Blocked by Other Phases
| Phase | Title | Blocker |
|-------|-------|---------|
| 3 | JSON Engine v1.0 | Phase 2 (error taxonomy definition) |

### 📌 OPTIONAL – Core Engine Complete Without These
| Phase | Title | Note |
|-------|-------|------|
| 12 | Patterns Library | Optional pattern templates; engine runs fine without |
| N+ | Advanced Features | Experimental research features; plug into stable core |

---

## Implementation Order (Recommended)

1. **✅ Phase 0-1**: Repo cleanup and schemas (foundation)
2. **🔵 Sonnet Design Work**: Phases 2, 4–7, 11 (design critical paths concurrently if possible)
3. **Phase 2**: Pipeline Executor (once designed; unlocks testing of later phases)
4. **Phases 3, 5**: JSON Engine, Tool Runtime (once Phase 2 defines error model)
5. **Phases 4, 6**: Agent Runtime, Memory System (design-dependent)
6. **Phase 7**: Router (integrates with phases 2–6)
7. **Phase 8**: Telemetry (wires through 2–7)
8. **Phase 9-11**: Plugins, LLM Adapters, Security
9. **Phases 13-14**: Example app, tests (final polish)
10. **Phase 12, N+**: Patterns and optional features (if time permits)

---

## Relationship to Canonical Docs

The plan now explicitly cross-references all three canonical documents:
* **AGENT_ENGINE_OVERVIEW** – High-level architecture and responsibilities
* **AGENT_ENGINE_SPEC** – Definition of Done and acceptance criteria
* **RESEARCH.md** – Detailed algorithmic and design details (referenced within phase descriptions)

Phases that require **Sonnet Design** will produce mini-design docs answering the specific "Design Gaps" listed, which will then guide Haiku implementation.
