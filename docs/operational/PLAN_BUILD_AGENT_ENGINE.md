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

# 🛠 **Phase 0 — Salvage & Refactor Legacy Components (Engine-Safe Only)**

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

# 🧱 **Phase 1 — Project Skeleton & Module Layout (Core Engine Only)**

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

# 🔌 **Phase 2 — Config Loader, Schema Validation & Manifest System**

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

---

# 🔀 **Phase 3 — Workflow Graph & Pipeline Executor**

**Goal:** Implement the DAG-based workflow engine as described in the overview.

### 3.1 Graph Representation

* Node types:

  * LLM agent node
  * Tool node
  * Decision node
  * Merge node
  * Feedback node
* Edge types: normal / error / fallback / policy-driven

### 3.2 DAG Validator

* Static checks for:

  * No cycles
  * All nodes reachable
  * Allowed transitions based on type
  * Schema-conforming

### 3.3 Pipeline Executor

* Stage execution loop
* Node input/output contract
* Routing hooks
* Telemetry emission

This produces the core execution model of Agent Engine.

---

# 🧠 **Phase 4 — Agent Runtime (LLM Adapter, Prompt Builder, Replies)**

**Goal:** Implement generic agent behavior, NOT pattern-specific logic.

### 4.1 LLM Adapter Interface

* Backend-agnostic:

  * OpenAI
  * Anthropic
  * Local models
* Unified:

  * cost tracking
  * token counting
  * timeouts
  * retries

### 4.2 Prompt Construction

* Deterministic prompt builder
* JSON schema for agent output
* No “magic” patterns (ReAct etc.)

### 4.3 JSON Response Enforcement

* Integrate salvaged JSON Engine
* Automatic retries with context clues
* Clear error surfaces

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

### 5.3 Tool Hooks

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

* Recency
* Hybrid scoring
* Embeddings (optional, plugin)
* ContextProfile configuration
* Deterministic selection

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

### 9.1 Hook Points

* before_task
* before_node
* after_node
* before_agent
* after_agent
* before_tool
* after_tool
* on_error
* on_task_complete

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

This is where the “awesome later” features belong.

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
