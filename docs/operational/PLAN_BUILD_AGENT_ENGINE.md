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

* Use your `docs/internal/phase_plan_prompt.txt` or `docs/internal/phase_plan_prompt_webgpt.txt` template.
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
10. Artifact Storage Subsystem
11. Engine Metadata & Versioning
12. Evaluation & Regression System
13. Performance Profiling & Metrics Layer
14. Security & Policy Layer
15. Provider / Adapter Management Layer
16. Debugger / Inspector Mode
17. Multi-Task Execution Model
18. CLI Framework (Reusable REPL)
19. Persistent Memory & Artifact Storage
20. Secrets & Provider Credential Management
21. Multi-Task Execution Layer
22. Packaging & Deployment Templates
23. Example App & Documentation

All other ideas are explicitly excluded and placed into **Future Work**.

---

# **4. Phase Details**

Below are the formal definitions of all phases, including goals, restrictions, and success criteria.

---

## Phases 0–18: Completed Implementation Summary

| Phase | Component | Tests | Status | Summary |
|-------|-----------|-------|--------|---------|
| 0 | Workspace Audit & Remediation | 384 | ✅ COMPLETE | Removed legacy pipelines, aligned with canonical DAG architecture |
| 1 | Canonical Schemas & Manifest Validation | 94 | ✅ COMPLETE | Implemented kind/role node model, DAG validator, context profiles |
| 2 | Engine Facade & DAG Loader | 57 | ✅ COMPLETE | Engine.from_config_dir(), manifest loading, exceptions, DAG construction |
| 3 | Task Model, History & Status Propagation | 33 | ✅ COMPLETE | Clone/subtask creation, lineage tracking, parent completion rules |
| 4 | Node Execution Skeleton & Tool Invocation | 32 | ✅ COMPLETE | NodeExecutor, DeterministicRegistry, ToolPlan execution |
| 5 | Router v1.0 (Deterministic DAG Routing) | 109 | ✅ COMPLETE | All 7 node roles (START/LINEAR/DECISION/BRANCH/SPLIT/MERGE/EXIT) |
| 6 | Memory & Context v1 | ~40 | ✅ COMPLETE | Task/project/global stores, context profiles, token budgeting |
| 7 | Error Handling, Status Propagation & Exit | ~25 | ✅ COMPLETE | Failure propagation, exit node semantics, continue_on_failure logic |
| 8 | Telemetry & Event Bus | 29 | ✅ COMPLETE | Event emission, task/node/routing/tool/context events |
| 9 | Plugin System v1 (Read-Only Observers) | 35 | ✅ COMPLETE | PluginBase, registry, TelemetryBus integration, isolation guarantees |
| 10 | Artifact Storage Subsystem | 25 | ✅ COMPLETE | NODE_OUTPUT/TOOL_RESULT artifacts, triple indexing, metadata |
| 11 | Engine Metadata & Versioning Layer | 28 | ✅ COMPLETE | SHA256 manifest hashes, engine version, schema version tracking |
| 12 | Evaluation & Regression System | 34 | ✅ COMPLETE | EvaluationCase, assertions (EQUALS/CONTAINS/SCHEMA_VALID/STATUS) |
| 13 | Performance Profiling & Metrics Layer | 32 | ✅ COMPLETE | Metrics collection (timer/counter/gauge), profiling hooks |
| 14 | Security & Policy Layer | 27 | ✅ COMPLETE | PolicyEvaluator, tool permissions, policy.yaml manifest |
| 15 | Provider / Adapter Management Layer | 22 | ✅ COMPLETE | AdapterMetadata, adapter registry integration, versioning |
| 16 | Debugger / Inspector Mode | 26 | ✅ COMPLETE | Task introspection (history/artifacts/events/summary) |
| 17 | Multi-Task Execution Model | 27 | ✅ COMPLETE | TaskManager query methods, isolation guarantees, sequential execution |
| 18 | CLI Framework (Reusable REPL) | 54 | ✅ COMPLETE | REPL with 10 built-in commands, profiles, session persistence |

**Cumulative: 1,127 tests passing across all phases**

---

# **Phase 19 — Persistent Memory & Artifact Storage**

*(Haiku implementation)*

## Status

**✅ COMPLETE (2025-12-11)**

## Goal

Provide durable persistence for global, project, and task memory while continuing to capture artifacts for every node execution.

## Canonical Design Decisions (v1)

### Storage Backends

**File-backed stores (JSONL)**:
* Format: JSON Lines (one JSON object per line)
* Location: `<root>/.agent_engine/memory/`
  * `task_store.jsonl`
  * `project_store.jsonl`
  * `global_store.jsonl`
* Append-on-write semantics
* Auto-flush to disk on every write
* No explicit save/load calls required

**SQLite-backed stores**:
* Single database per project: `<root>/.agent_engine/memory/memory.db`
* Tables: `task_memory`, `project_memory`, `global_memory`, `artifacts`
* Columns: `id` (PK), `task_id`, `project_id`, `store`, `payload` (JSON), `created_at`, `tags`, `metadata`
* Auto-commit on every write

### Retention Policies

**Count-based (v1 only)**:
* `max_items` per store
* Automatic enforcement (delete oldest when limit exceeded)
* Time-based and size-based retention are future work

**Configuration Example**:
```yaml
memory:
  task_store:
    backend: "file"  # or "sqlite"
    retention:
      max_items: 1000
  project_store:
    backend: "sqlite"
    retention:
      max_items: 5000
  global_store:
    backend: "sqlite"
    retention:
      max_items: 10000
```

## Tasks

* Implement `JsonLinesBackend` and `SQLiteBackend` classes
* Extend `memory.yaml` schema with `backend` and `retention` fields
* Update `MemoryStore` to use persistent backends with auto-save
* Extend `ArtifactStore` with optional persistence
* Create comprehensive tests (30+ tests required)
* Ensure memory survives engine restart
* Keep DAG semantics unchanged

## Success Criteria

* ✅ JSONL backend works with automatic flushing
* ✅ SQLite backend works with automatic commits
* ✅ Retention policies enforced automatically
* ✅ Memory survives engine restart
* ✅ Artifacts persist to storage
* ✅ 30+ tests all passing
* ✅ No regressions in existing tests
* ✅ Telemetry records reflect persistence metadata

# **Phase 20 — Secrets & Provider Credential Management**

*(Haiku implementation)*

## Goal

Securely load secrets, map them to provider credentials, and integrate the material with the adapter registry without touching the router.

## Canonical Design Decisions (v1)

### Credential Sources (v1)

**Supported sources**:
* Environment variables (primary method)
* Plain files on disk (with OS-level file permissions for security)
* **NO encryption required** in v1

**Not supported in v1** (future work):
* Encrypted files
* External key vaults (AWS KMS, HashiCorp Vault, etc.)

### provider_credentials.yaml Format

```yaml
provider_credentials:
  - id: "anthropic_sonnet"       # Logical credential ID
    provider: "anthropic"         # Provider name
    auth:
      type: "api_key"            # ONLY type supported in v1
      source: "env" | "file"     # Where to load secret from

      # If source == "env":
      env_var: "ANTHROPIC_API_KEY"

      # If source == "file":
      file_path: "/path/to/key.txt"
      file_key: "api_key"        # Optional: JSON/YAML key within file

    config:                      # Optional provider config
      base_url: "https://api.anthropic.com"
      default_model: "claude-sonnet-4"
```

**Supported credential types in v1**:
* `api_key` ONLY
* OAuth tokens, certificates, SSH keys are future work

### Security Model

* File-based secrets rely on OS-level file permissions (chmod 600)
* No cryptographic layer required in v1 code
* Secrets NEVER appear in telemetry or logs (only metadata)
* Document security best practices in SECURITY.md

## Tasks

* Create credential schemas (`AuthConfig`, `ProviderCredential`)
* Implement credential loader with env var and file support
* Create `CredentialProvider` class
* Wire credentials into adapter registry
* Emit telemetry for credential loads (metadata only, NO secrets)
* Create comprehensive tests (25+ tests required)
* Document security best practices

## Success Criteria

* ✅ Load credentials from environment variables
* ✅ Load credentials from plain files (text, JSON, YAML)
* ✅ provider_credentials.yaml schema implemented
* ✅ Credentials injected into adapters transparently
* ✅ Telemetry emits metadata only (no secret values)
* ✅ 25+ tests all passing
* ✅ SECURITY.md documentation created
* ✅ No secrets leak into DAG definitions or telemetry

# **Phase 21 — Multi-Task Execution Layer**

*(Haiku implementation)*

## Goal

Enable cooperative scheduling of multiple concurrently running Tasks with isolated memory, history, telemetry, and artifacts.

## Canonical Design Decisions (v1)

### Concurrency Model (v1)

**Sequential execution for v1**:
* `max_concurrency = 1` by default
* No threads, asyncio, or multiprocessing required
* Implement scheduler abstraction with queue and lifecycle tracking
* True parallelism is **future work**

**Rationale**:
* Isolation semantics already handled by Phase 17
* Phase 21 adds explicit multi-task coordination, queueing, and state tracking
* Parallel execution can be built on same scheduler API in future versions

### scheduler.yaml Format

```yaml
scheduler:
  enabled: true                 # Default: true
  max_concurrency: 1            # v1 default (sequential)
  queue_policy: "fifo"          # ONLY policy in v1
  max_queue_size: 100           # Optional; null = unbounded
```

**Future work** (not implemented in v1):
```yaml
  rate_limit:                   # Reserved for future
    requests_per_minute: 60
    burst: 10
```

### Task States

* `QUEUED` - Task in queue, not yet running
* `RUNNING` - Task currently executing
* `COMPLETED` - Task finished successfully
* `FAILED` - Task finished with failure

### Scheduler Semantics

* **FIFO queueing** - tasks execute in order received
* **max_queue_size enforcement** - reject new tasks when queue full
* **Sequential execution** - dequeue and run one task at a time
* **State tracking** - all task states queryable
* **Telemetry events** - task_queued, task_dequeued, queue_full

## Tasks

* Create scheduler schemas (`SchedulerConfig`, `TaskState`, `QueuedTask`)
* Implement scheduler loader with default config
* Create `TaskScheduler` class with FIFO queue
* Integrate scheduler with Engine
* Add CLI commands: `/queue`, `/run-queue`, `/queue-status`
* Create comprehensive tests (30+ tests required)
* Maintain Phase 17 isolation guarantees

## Success Criteria

* ✅ Scheduler queues tasks (FIFO order)
* ✅ Sequential execution (one task at a time)
* ✅ max_queue_size enforced
* ✅ Task state tracking (queued→running→completed/failed)
* ✅ Telemetry events emitted
* ✅ Engine exposes scheduling API (`enqueue`, `run_queued`)
* ✅ CLI commands work (`/queue`, `/run-queue`, `/queue-status`)
* ✅ 30+ tests all passing
* ✅ Phase 17 isolation maintained (no shared mutable state)

# **Phase 22 — Packaging & Deployment Templates**

*(Haiku implementation, optional)*

## Goal

Offer recommended packaging and deployment templates that capture layout, manifest versions, environment bootstrap scripts, and reproducible guidance.

## Tasks

* Document the recommended repository layout, manifest versioning strategy, and environment bootstrap commands for Agent Engine projects.
* Provide deployment templates or scripts that reproduce the same runtime stack across environments.
* Link packaging metadata to telemetry/metadata stores so deployments can be validated post-facto.
* Keep the templates optional and separate from core DAG semantics.

## Success Criteria

* Teams can follow the templates to reproduce deployments reliably.
* Deployment metadata (versions, hashes, bootstrap commands) is recorded for auditability.
* Templates do not interfere with canonical routing or existing nodes.

# **Phase 23 — Example App & Documentation**

*(Haiku implementation)*

## Goal

Provide a minimal, canonical reference implementation with complete documentation.

## Canonical Design Decisions (v1)

### Diagram Format

**Use Mermaid** as primary diagram format:
* Embedded directly in Markdown files
* Each diagram includes:
  * Short descriptive caption
  * Textual explanation before/after Mermaid block
  * Ensures docs are understandable when diagrams can't render

**Required diagrams**:
1. DAG structure (nodes + edges)
2. Node lifecycle/state transitions
3. Routing semantics (all 7 node roles)
4. Task lineage (parent/clone/subtask)
5. Plugin flow and telemetry events

ASCII art is optional, not required.

### Mini-Editor Scope

**CLI-integrated example workflow** (NOT standalone app):
* Uses Phase 18 CLI framework
* Demonstrates:
  * Custom CLI profile definition
  * File attachment mechanics
  * Engine.run() for content creation/updates
  * Feedback/revision loops via session history

**Workflow features**:
* Accept plain-language drafting instructions
* Create/update Markdown files by default
* Generate structured summary (title, length, sections, tone)
* Iterative refinement via natural language edits
* Use existing CLI commands (/attach, /history, /retry, /edit-last)

**NOT required**:
* Full-screen editor UI
* Standalone CLI separate from Phase 18 framework
* Extensions beyond CLI framework semantics

## Tasks

### Documentation

* **ARCHITECTURE.md**: All 5 Mermaid diagrams with explanations
* **README.md**: Complete feature list, quick start, phase status (0-23 complete)
* **DEVELOPER_GUIDE.md**: Combined setup + first workflow walkthrough
* **API_REFERENCE.md**: Complete public API documentation

### Mini-Editor Example App

* Directory: `examples/mini_editor/`
* Files:
  * `config/workflow.yaml` - document creation/editing workflow
  * `config/agents.yaml` - editor agent definition
  * `config/tools.yaml` - file I/O tools
  * `config/memory.yaml` - document memory
  * `config/cli_profiles.yaml` - "mini_editor" profile
  * `config/schemas/` - document schemas
  * `run_mini_editor.py` - entry point script
  * `README.md` - mini-editor documentation

### Workflow Design

```
START → normalize_request
  ↓
DECISION → create_new vs edit_existing
  ↓
AGENT → draft_document (creates/updates .md file)
  ↓
AGENT → generate_summary (structured summary)
  ↓
EXIT → return_summary
```

Feedback loops via CLI /retry and /edit-last commands.

### Verification

* Grep entire codebase for "pipeline" references
* Ensure no deprecated features remain
* Verify docs match canonical specs

## Success Criteria

* ✅ All 5 Mermaid diagrams complete and correct
* ✅ Mini-editor runs end-to-end
* ✅ Mini-editor demonstrates CLI integration
* ✅ Tutorial walks through complete workflow
* ✅ API reference is complete
* ✅ README updated with all 23 phases complete
* ✅ No "pipeline" references in documentation
* ✅ 20+ tests all passing
* ✅ Documentation internally consistent with canonical specs

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

 * All phases 0–23 are implemented
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
