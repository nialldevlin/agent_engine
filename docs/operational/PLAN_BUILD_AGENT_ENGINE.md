# **PLAN_BUILD_AGENT_ENGINE.md**

## *Canonical Build Plan for Agent Engine v1*

### *LLM-Safe, Deterministic, Implementation-Ready*

---

# **0. Purpose of This Document**

This document defines the **complete phase plan** for implementing **Agent Engine v1**, using the canonical architectural contract described in:

* **AGENT_ENGINE_OVERVIEW.md** 
* **AGENT_ENGINE_SPEC.md** 
* **PROJECT_INTEGRATION_SPEC.md** 
* **RESEARCH.md** (conceptual background only)

The goal of this build plan is:

* To provide a **deterministic, hallucination-resistant** implementation roadmap
* To ensure LLM agents *cannot* deviate from canonical semantics
* To allow implementation using *any* agent suite (Claude Code Sonnet, Haiku, Qwen 7B, etc.)
* To declare exactly what constitutes **v1 complete**
* To isolate all speculative or “not strictly required” features into **Future Work**

This document **does not** contain code.
This document **must** remain stable and unambiguous during development.

---

# **1. How to Use This Build Plan With LLM Agents**

## **1.1 Sonnet (PLAN MODE)**

Use Claude Code **Sonnet** to generate a detailed `PHASE_<id>_IMPLEMENTATION_PLAN.md` for phases:

* Phase 0
* Phase 1
* Phase 2
* Phase 4
* Phase 5
* Phase 6
* Phase 9

Because these phases affect core structure, they require Sonnet’s deeper reasoning and long-context planning.

### When invoking Sonnet:

* Use your `phase_plan_prompt.txt` or `phase_plan_prompt_webgpt.txt` template.
* Provide only the files mentioned in `<Context>`.
* Require Sonnet to output a **step-by-step implementation brief** with:

  * explicit file paths
  * explicit invariants
  * *no* code
  * HUMAN vs LLM division of labor
* Reject any output that:

  * invents pipelines
  * invents node roles
  * invents routing mechanisms
  * modifies canonical semantics
  * alters the architecture

## **1.2 Haiku (ACT MODE)**

Use Claude Code **Haiku** (or Qwen 7B locally) to execute implementation steps:

* Small, local code changes
* File updates specified by the Sonnet Phase Plan
* Test additions or fixes
* Manifest normalization
* Context assembly wiring
* Telemetry hook insertion
* Plugin system scaffolding

Haiku excels when:

* The task is extremely well-scoped
* The steps are explicitly defined
* No long reasoning is required

## **1.3 Restrictions for All LLM Agents**

LLMs must **not**:

* invent or modify engine semantics
* create pipelines or pipeline selectors
* treat tools as nodes
* add new node roles or kinds
* introduce loops inside the DAG
* introduce unapproved routing logic
* mutate tasks from plugins
* modify canonical manifest fields
* implement “learned” routing outside Future Work

LLMs **must**:

* preserve the DAG as the sole routing structure
* preserve node roles and their canonical behaviors
* follow the universal status model
* follow strict schema validation
* maintain deterministic execution

---

# **2. Build Philosophy and Guarantees**

This build plan enforces:

### **Determinism**

Execution must be exactly reproducible for given inputs and manifests.

### **Single Source of Truth**

The canonical documents define **everything** about:

* Routing
* Node roles
* Task lifecycle
* Status semantics
* Context assembly
* Tools
* Memory layering
* Observability

### **Testability**

Every phase ends with a clear, unambiguous definition of “done.”

### **No Surprises**

All routing behavior must come explicitly from the workflow DAG.
There is no implicit routing and no hidden fallback logic.

---

# **3. Phase Overview (v1 Complete)**

Agent Engine v1 consists of the following phases:

0. Workspace Audit & Remediation
1. Canonical Schemas & Manifest Validation
2. Engine Facade & DAG Loader
3. Task Model, History, and Status Propagation
4. Node Execution Skeleton & Tool Invocation
5. Router v1.0 (Deterministic DAG Routing)
6. Memory & Context v1
7. Error Handling, Status Propagation & Exit Behavior
8. Telemetry & Event Bus
9. Plugin System v1 (Read-Only Observers)
10. Example App & Documentation

All other ideas are explicitly excluded and placed into **Future Work**.

---

# **4. Phase Details**

Below are the formal definitions of all phases, including goals, restrictions, and success criteria.

---

# **Phase 0 — Workspace Audit & Remediation**

*(Sonnet-plan + Haiku implementation)*

## Goal

Bring the workspace into exact alignment with canonical architecture and remove all legacy or conflicting structures.

## Tasks

### 1. Remove all non-canonical routing concepts

* Delete or quarantine any `pipelines.yaml` files.
* Remove any code referencing “PipelineExecutor”, “pipeline selection”, or multi-pipeline routing.
* DAG (`workflow.yaml`) becomes the **sole routing definition**.

  * Matches PROJECT_INTEGRATION_SPEC. 

### 2. Eliminate all legacy code

* Ensure no imports from previous “king_arthur” or pipeline-era modules remain.
* Ensure tests do not reference deprecated pipeline semantics.

### 3. Refactor file names / modules to match DAG-only semantics

* `pipeline_executor.py` → `dag_executor.py` (or equivalent).
* Confirm no file names or comments describe pipelines.

### 4. Validate manifests directory structure

* Must match PROJECT_INTEGRATION_SPEC exactly. 

### 5. Ensure schemas & registry align with canonical manifests

* Only register: workflow, agents, tools, memory, plugins (optional), schemas.
* No pipeline schema.

## Success Criteria

* `import agent_engine` works without referencing any legacy features.
* All schema registration matches canonical manifest list.
* No code path depends on pipelines.
* Workspace ready for implementation of Phase 1.

## Status

**✅ COMPLETE (2025-12-09)**

Detailed implementation plan: [PHASE_0_IMPLEMENTATION_PLAN.md](./PHASE_0_IMPLEMENTATION_PLAN.md)

- All file operations completed (pipelines.yaml, stages.yaml deleted; dag_executor.py created)
- All schemas updated (Pipeline deprecated, removed from registry)
- All tests updated and passing (384 tests)
- All code references cleaned (no PipelineExecutor, choose_pipeline, pipeline_id)
- All completion criteria verified

Workspace is now aligned with canonical architecture and ready for Phase 1.

---

# **Phase 1 — Canonical Schemas & Manifest Validation**

*(Sonnet-plan + Haiku implementation)*

## Goal

Implement all canonical data structures and manifest schemas.

## Status

**✅ COMPLETE (2025-12-09)**

Detailed implementation plan: [PHASE_1_IMPLEMENTATION_PLAN.md](./PHASE_1_IMPLEMENTATION_PLAN.md)

## Summary of Changes

### Core Schema Updates
- **Node Schema**: Migrated from legacy `StageType` to canonical `kind` (agent/deterministic) + `role` (start/linear/decision/branch/split/merge/exit) model
- **Edge Schema**: Simplified to canonical `(from_node_id, to_node_id, label?)` format; removed `EdgeType` enum
- **Task Schema**: Separated `lifecycle` (pending/running/completed) from `status` (success/failure/partial); added lineage tracking and memory references
- **ContextProfile Schema**: New canonical schemas for context assembly configuration
- **Tool Schema**: Enhanced with canonical permission fields (allow_network, allow_shell, filesystem_root)
- **WorkflowGraph Schema**: Updated to use `nodes` field and determine start/exit nodes from role-based rules

### Validation Implementation
- **DAG Validator**: Comprehensive validation enforcing all canonical invariants:
  - Kind-role constraints (START/EXIT must be DETERMINISTIC)
  - Context field validation (profile ID, "global", or "none")
  - Agent ID validation (required for AGENT kind)
  - Default start validation (exactly one START node with default_start=True)
  - Role-based edge count constraints for all 7 node roles
  - Acyclicity, reachability, and node connectivity checks

### Test Coverage
- **65 new canonical schema validation tests** covering:
  - 20 Node schema tests
  - 7 Edge schema tests
  - 11 Task schema tests
  - 12 ContextProfile schema tests
  - 15 comprehensive DAG validation tests
- **94 total schema validation tests** (new + existing) all passing
- **458 total project tests** all passing

### Files Modified
- Schema files: `stage.py`, `workflow.py`, `task.py`, `memory.py`, `tool.py`
- Runtime files: `router.py`, `config_loader.py`, `dag_executor.py`, and 5+ others
- Test files: Updated all tests to use canonical schemas
- Registry: Updated schema registry and exports

### Acceptance Criteria Met
✅ All nodes use `kind` and `role` (no `StageType` references)
✅ All edges use canonical model (no `EdgeType` references)
✅ Task has separate lifecycle and status fields
✅ Task has lineage and memory reference fields
✅ ContextProfile schema fully implemented
✅ DAG validator enforces all canonical invariants
✅ All canonical schemas registered and exported
✅ Comprehensive test coverage (65 new tests)
✅ All documentation references canonical specs
✅ 458/458 tests passing

---

# **Phase 2 — Engine Facade & DAG Loader**

*(Sonnet-plan + Haiku implementation)*

## Goal

Provide a fully functional `Engine.from_config_dir()` capable of loading a canonical project.

## Tasks

### 1. Engine façade

Implement public API exactly as PROJECT_INTEGRATION_SPEC defines:
`Engine.from_config_dir(path)` and `Engine.run(input)`.


### 2. Manifest loader

* Load workflow, agents, tools, memory, schemas, plugins.
* Validate using schemas from Phase 1.

### 3. DAG construction

* Build in-memory DAG with nodes + edges strictly following canonical semantics.
* Verify structural constraints.

### 4. Error reporting

* Provide structured, helpful manifest load errors.

## Success Criteria

* Minimal example config loads without errors.
* Invalid configs produce deterministic errors.

---

# **Phase 3 — Task Model, History, and Status Propagation**

*(Haiku implementation, Sonnet optional)*

## Goal

Implement the canonical Task data structure and lineage rules.

Matches AGENT_ENGINE_SPEC §2.1 and OVERVIEW §1.1.

## Tasks

* Implement status model (`success`, `failure`, `partial`).
* Implement history entries recording input, output, tools, timestamps.
* Implement lineage rules: clones & subtasks.
* Parent completion rules for Branch and Split.

## Success Criteria

* Tests validate correct lineage and status propagation.
* History is complete and deterministic.

---

# **Phase 4 — Node Execution Skeleton & Tool Invocation**

*(Sonnet-plan + Haiku implementation)*

## Goal

Implement the lifecycle of a single node execution.

Matches AGENT_ENGINE_SPEC §3.2.


## Tasks

* Context assembly (using Phase 6 hooks later).
* Deterministic vs agent-driven execution paths.
* Schema validation of node outputs.
* ToolPlan invocation & tool permission enforcement.
* Failure behavior (`continue_on_failure`, `fail_on_failure`).

## Success Criteria

* Correct execution of simple linear workflows with tools + LLMs.
* Output validation errors handled deterministically.

---

# **Phase 5 — Router v1.0 (Deterministic DAG Routing)**

*(Sonnet-plan + Haiku implementation)*

## Goal

Implement the canonical DAG router.
Matches AGENT_ENGINE_SPEC §3.1 and OVERVIEW §1.3–1.5.

## Tasks

### Routing semantics per role

* Start: select default or explicit
* Linear: single outbound
* Decision: interpret output → pick labeled edge
* Branch: spawn **clones**
* Split: spawn **subtasks**
* Merge: wait for all inbound results
* Exit: halt (read-only)

### Error routing

* Use explicit **error edges only**
* No secret fallback paths

## Success Criteria

* All canonical node role rules behave exactly as specified.
* No routing occurs outside DAG edges.
* Branch/split/merge scenarios pass tests.

---

# **Phase 6 — Memory & Context v1**

*(Sonnet-plan + Haiku implementation)*

## Goal

Implement memory stores and the context assembler.

Matches OVERVIEW §1.5 and PROJECT_INTEGRATION_SPEC memory.yaml.

## Tasks

* Implement task/project/global memory.
* Implement context profiles with retrieval policies.
* Implement token budgeting + HEAD/TAIL compression.
* Implement context assembly for each node execution.

## Success Criteria

* Deterministic context slices for any task/node.
* Tests verify token budgeting + retrieval logic.

---

# **Phase 7 — Error Handling, Status Propagation & Exit Behavior**

*(Haiku implementation)*

## Goal

Finalize all error-handling semantics and ensure exit nodes behave canonically.

Matches AGENT_ENGINE_SPEC §3.4 and OVERVIEW semantics.

## Tasks

* Node-level failure logic
* Task-level failure/partial propagation
* Merge interaction with failures
* Exit node behavior (structured output only, no LLM, no tools)

## Success Criteria

* Failures and partials propagate exactly per spec.
* All exit nodes behave read-only and deterministic.

---

# **Phase 8 — Telemetry & Event Bus**

*(Haiku implementation, Sonnet optional)*

## Goal

Add observability hooks for internal introspection and plugin consumption.

Matches AGENT_ENGINE_SPEC §6.


## Tasks

* Implement event bus
* Emit events for:

  * task start/end
  * node start/end
  * routing decisions
  * tool calls
  * context assembly
  * clone/subtask creation
* Attach telemetry to DAG executor + router + node executor

## Success Criteria

* All major engine actions produce deterministic events.
* Telemetry tests confirm correct event payloads.

---

# **Phase 9 — Plugin System v1 (Read-Only Observers)**

*(Sonnet-plan + Haiku implementation)*

## Goal

Implement plugin architecture for read-only engine observers.

Matches PROJECT_INTEGRATION_SPEC plugins.yaml semantics.


## Tasks

* `plugins.yaml` loader
* Plugin interface:
  `on_event(event: EngineEvent) -> None`
* Register plugins with event bus
* Guarantee plugins:

  * cannot mutate task state
  * cannot modify routing
  * cannot modify the DAG
  * cannot access internal runtime modules directly

## Success Criteria

* Plugins receive deterministic events.
* Engine remains fully deterministic regardless of plugins.
* Plugin failures never alter routing or task behavior.

---

# **Phase 10 — Example App & Documentation**

*(Haiku implementation)*

## Goal

Provide a minimal, canonical reference implementation.

## Tasks

* Build an example project with:

  * workflow.yaml
  * agents.yaml
  * tools.yaml
  * memory.yaml
  * schemas/
  * plugins.yaml (stub)
* Add CLI runner demonstrating:
  `Engine.from_config_dir().run(input)`
* Update documentation to match AGENT_ENGINE_SPEC & PROJECT_INTEGRATION_SPEC.
* Provide diagrams of:

  * DAG structure
  * node lifecycle
  * routing semantics
  * task lineage
  * plugin flow

## Success Criteria

* Example app runs end-to-end.
* Docs are internally consistent and match canonical architecture.
* No reference to pipelines or deprecated features appears.

---

# **5. Non-Goals for v1**

To prevent LLM drift or hallucination:

Agent Engine v1 **must not** implement:

* learned or MoA routing
* active plugins that influence routing
* multi-DAG routing
* dynamic pipeline selection
* retry loops inside the DAG
* conversational loops inside the DAG
* automatic tool selection
* schema inference
* dynamic DAG modification

All of these belong strictly in **Future Work**.

---

# **6. Future Work (Beyond v1 Scope)**

This section collects all speculative or research-oriented ideas.
They are explicitly *not part of the v1 build* and must not be implemented by LLMs during v1.

## **FW-1: Multi-Agent Patterns Library**

(committee, supervisor/worker, debate, reviews)
These patterns must be implemented *outside* the DAG using the public Engine API.

## **FW-2: Learned / MoA Router Variants**

Using telemetry, classifiers, or model-of-agents routing.
These must wrap the deterministic router rather than replace it.

## **FW-3: Adaptive Context Budgeting**

Auto-tuning context profiles based on token usage and telemetry.

## **FW-4: Advanced Plugin Types**

Plugins that propose suggestions, not decisions:

* “Consider using agent X instead of Y”
* “Consider alternate start node”
  These should only be enabled via explicit user control.

## **FW-5: Distributed Execution & Remote Nodes**

Execution of deterministic nodes or agent nodes across distributed backends.

## **FW-6: Interactive Debugging & Replay Tools**

UI or CLI tools for navigating task history and replaying per-node execution.

## **FW-7: DAG Authoring Tools**

Visual editors, schema-aware IDE plugins, etc.

---

# **7. Definition of Done for Agent Engine v1**

Agent Engine is **complete** when:

* All phases 0–10 are implemented
* All canonical documents are satisfied
* DAG execution matches the formal semantics exactly
* Tool invocation, routing, and context assembly are deterministic
* Status propagation rules behave per spec
* Telemetry emits complete traces
* Plugins can observe but never influence execution
* Example app runs successfully
* All tests pass with no reference to legacy features

---

# **End of PLAN_BUILD_AGENT_ENGINE.md**
