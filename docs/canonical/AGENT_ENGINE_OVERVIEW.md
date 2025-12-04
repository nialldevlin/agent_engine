# Agent Engine Overview
_Last updated: 2025-12-03_

## 1. Overview

The **Agent Engine** is an extensible, modular framework for building
multi-agent LLM applications. It provides clean internal data models, strict
schema enforcement, and standardized execution behavior derived from external
configuration using YAML or JSON. The engine handles everything except raw LLM
API calls: prompt construction, task state management, agent
orchestration, tool execution, memory layers, workflow graphs, routing, and
event telemetry.

Instead of embedding logic directly into code, the engine is configured through
manifests defining agents, pipelines, workflow graphs, tools, memory settings,
and plugin rules. This allows the engine to be used for any agent system using
YAML or JSON to configure the engine with any intended functionality, define
"personality", and create any desired LLM application.

The engine handles all of the following:

* Agents
* Tasks
* Tools
* Memory
* Data Retrieval
* Context Assembly
* Workflow Graphs
* Pipelines
* Routing
* Plugin Hooks
* Telemetry & Events

The engine consists of these components:

* Config Loader
* Core Data Models
* Task Manager
* Workflow Graph
* Pipeline Executor
* Router
* Agent Runtime
* Tool Runtime
* Memory and Retrieval Layer
* JSON Engine
* Telemetry/Event Bus
* Plugin/Hook System
* LLM Backend Adapter
* Patterns Library (optional manifest templates such as committee, supervisor, chat; none are enabled unless explicitly authored)

---

## 2. Engine Responsibilities

The Agent Engine performs three high-level operations:

1. **Load all definitions** (agents, tools, workflow graph, pipelines, etc.)
   from YAML/JSON manifests.
2. **Convert a user request into a Task**, the stateful unit of work.
3. **Execute the Task through the workflow graph**, using routing, pipelines,
   agents, tools, memory, and plugins.

Everything else—schema enforcement, tool safety, JSON validation, context
construction, memory retrieval—supports these operations.

---

## 3. Configuration

The engine has configurations to allow extensibility for:

* high-level engine configuration
* workflow graph definition (stages and transitions)
* pipeline definitions (paths through the workflow graph)
* agents
* tools
* modes
* enabled plugins and hooks
* memory

All files may be YAML or JSON.
**YAML is converted to JSON**, and internal storage is JSON-shaped structures
only with strict schemas.
Every manifest must validate against the published JSON Schemas; no implicit or undeclared fields are allowed.

---

## 4. Tasks

A **Task** is the engine’s stateful record of work. It carries everything needed
through the workflow. Tasks act as the glue between stages. Tasks arise from
prompts but are not tied to them; a prompt may generate several tasks, and a
task may span multiple prompts.

A Task:

* describes *what* must be done
* tracks pipeline progress
* records all stage outputs
* holds related memory/context
* stores telemetry, decisions, overrides, and tool outputs
* links to subtasks or parent tasks if needed

---

## 5. Workflow Graph & Pipelines

The **Workflow Graph** is the complete map of stages and allowed routing
decisions. **Pipelines** are specific traversals through this graph.

The workflow graph consists of nodes (stages) and edges (transitions) and is
represented as a **directed acyclic graph (DAG)**. This means:

* edges have a direction (from one stage to another)
* there are **no cycles** (no path that returns to a previous stage)
* every valid execution path moves forward and eventually terminates

User input is turned into a Task, and the pipeline routes that Task through the
graph. A stage is an operation on the Task, resulting in progress toward the
task’s goal or manipulation of the workspace. A stage may be a deterministic
tool call or, more commonly, an agent call. All stage interactions are
structured and schema-enforced.

Conceptually:

* any node with a single outgoing edge is a **transformation**
* any node with multiple outgoing edges is a **decision**
* decision nodes may be deterministic or agent-driven
* a pipeline that encounters no decisions is linear

### 5.1 Workflow Graph

A **Workflow Graph** is a directed acyclic graph (DAG) containing:

* **Nodes (Stages)**, including:
  * **Start nodes** – entry points for pipelines
  * **End nodes** – terminal nodes with no outgoing edges
  * **Work stages** – agent stages and tool stages that perform work
  * **Decision stages** – stages that choose among multiple outgoing edges based
    on Task state (deterministic rules or agent output)
  * **Merge stages** – stages that join multiple incoming paths into one
* **Edges (Transitions)**:
  * directed connections from one node to another
  * controlled, validated transitions that define legal execution paths

Constraints:

* the graph is acyclic (no cycles allowed)
* every pipeline must start at a valid start node and end at an end node
* from each start node, there must be at least one path to some end node
* stages should be either pure transformations (single outgoing edge) or decisions
  (multiple outgoing edges), but not both at the same time

Because the graph is a DAG, it can be statically validated, is guaranteed to
terminate for well-formed pipelines, and is easier to debug and reason about.
Routers may only select among pipelines explicitly defined in manifests; there is no implicit or self-directed routing.

Retries, refinements, or "loop-like" behaviors are implemented at the **stage
or pattern level** (for example, an agent stage that internally retries up to N
times), not by creating cycles in the workflow graph itself.

### 5.2 Stages

A **Stage** represents one step in the workflow and follows a fixed lifecycle:

1. **Prepare Input**
   * assemble context: user input, prior stage outputs, memory, retrieved
     documents, mode flags, and agent or tool configuration
2. **Call Agent or Deterministic Function**
   * for an **agent stage**:
     * render prompts
     * call the LLM via the Agent Runtime
     * enforce JSON/schema
   * for a **tool stage**:
     * validate inputs
     * execute the tool
     * validate outputs
3. **Handle Output**
   * store results into the Task
   * update Task status or metadata
   * optionally set flags that influence downstream routing

Stages may participate in:

* linear flows (single in, single out)
* decision flows (single in, multiple out via downstream Decision stage)
* merge flows (multiple in, single out)

### 5.3 Pipelines

A **Pipeline** is the traversal of a Task through the workflow graph along a
specific **acyclic path** (or branching tree that ultimately converges and
terminates).

A pipeline definition includes:

* **entry stage** (start node)
* **allowed sequence of stages** and transitions
* **termination rules**, typically defined by reaching an end node
* **fallback behavior** (e.g., alternate end nodes for error or degraded modes)

The router chooses which pipeline to run for a Task and how that pipeline is
instantiated within the global workflow graph (for example, which agents are
assigned to which stages and which optional branches are enabled).

---

## 6. Routing

The **Router** determines:

* which pipeline a Task should follow
* which stages in the workflow graph will be traversed
* which agent handles each agent stage
* how to apply user overrides
* whether to use alternate agent variants
* how to incorporate scoring/evolution
* fallback agent selection if errors happen
* how to produce a routing trace for debugging

Routing considers:

* the Task (input, metadata, mode flags)
* agent capabilities and constraints
* the workflow graph (available stages and transitions)
* pipeline definitions
* project rules and policies
* plugin overrides

The router may be purely rule-based or may consult a specialized routing agent
that proposes choices within the constraints of the DAG. All routing decisions
are recorded on the Task for inspection and debugging.

---

## 7. Agent Runtime

The Agent Runtime is responsible for:

* rendering prompts
* combining context
* calling the LLM backend
* handling retries and JSON repair
* enforcing schemas
* producing structured outputs
* attaching metadata (token counts, timing, cost)
* emitting events to telemetry

---

## 8. Tool Runtime

The Tool Runtime handles:

* tool invocation
* input validation
* permission checks (filesystem/network)
* execution (Python, shell, HTTP, custom)
* output validation
* writing results to the Task
* generating Tool Events for telemetry

Tools allow agents to:

* read/write files
* run search
* query environments
* execute transformations
* call external APIs

Tools must follow strict schemas to avoid ambiguous behavior and pass through
the security and permissions layer. Tool execution is deterministic: agents can only request tools via structured `ToolPlan` JSON, and every tool enforces consent and workspace boundaries before running.

---

## 9. Memory and Context

LLMs have no built-in memory.
The engine constructs memory layers to supply context to agents.

### 9.1 Context

Context = everything the agent sees when it runs. The Context Assembler follows explicit, deterministic policies declared in manifests; it never adds data that was not requested by the configured context profile.

* prompt template
* system instructions
* user messages
* stage outputs
* memory history
* retrieved documents
* tool observations
* mode flags
* agent configuration
* routing notes

A Context Assembler component is responsible for collecting and packaging this
information for each stage invocation strictly according to the configured profile (no implicit Stage 4 heuristics).

### 9.2 Memory Layers

#### Conversation Memory

* recent messages
* summarized older messages
* structured state extracted from history

#### Long-Term Knowledge Memory (RAG)

* vector database of documents, files, research, preferences
* semantic retrieval
* supports cross-task recall

#### Agent State Memory

* persistent JSON blob per agent
* goals, partial results, reasoning structures
* not user-visible

#### Profile Memory

* user preferences
* styles
* long-running projects
* saved contexts

#### Tool/Environment Memory

* file modifications
* code edits
* environment queries

Memory is retrieved per stage and inserted into the context batch according to
pipeline and agent configuration. These conceptual layers are realized via the task/project/global memory stores; do not assume a separate legacy subsystem exists.

---

## 10. JSON Engine

The JSON Engine ensures reliability:

* schema enforcement
* parse errors → structured `EngineError`
* repair strategies
* multi-pass retries
* deterministic fallback behaviors
* schema-based transformations
* agent output normalization

This is critical for preventing pipeline collapse and keeping all agent and tool
outputs structured and predictable.

---

## 11. Telemetry and Event Bus

Every significant action emits an Event:

* task created
* stage started/finished
* agent called
* tool called
* memory retrieved
* pipeline transitions
* errors & recoveries
* cost/timing metrics

Plugins can listen to events for:

* logging
* analytics
* scoring
* evolution
* auditing
* debugging
* external monitoring integrations

The Event Bus is the observability backbone of the engine.

---

## 12. Plugin and Hook System

Plugins add custom functionality without modifying the core engine.

Hook surfaces include:

* before/after task
* before/after stage
* before/after agent
* before/after tool
* memory events
* routing decisions
* pipeline transitions
* errors

Plugins allow developers to build any system on top of the base engine. The
engine stays lightweight while plugins provide heavy customization.

---

## 13. LLM Backend Interface

The engine is backend-agnostic.
An `LLMClient` interface defines standard methods:

* `generate()`
* `stream_generate()`
* backend-specific configuration
* token counting
* cost estimation (optional)

Adapters can be built for:

* OpenAI
* Anthropic
* Google
* Mistral
* Local models (llama.cpp, vLLM, etc.)

Multiple backends can coexist in a single project (for example, one model for
reasoning and another for fast tool-style calls), configured via manifests.

---

## 14. Security and Permissions

All tools used by agents go through a permissions layer that requires explicit
consent, with engine-level defaults and configurable per-project and per-agent
defaults.

The security system can control:

* filesystem permissions (read-only, write, restricted paths)
* network permissions
* shell execution toggles
* environment visibility
* tool whitelists per agent
* safe-mode flags (`analysis_only`, `dry_run`)

Security is both a manifest concern and a runtime enforcement concern.

---

## 15. Summary

The Agent Engine is a modular, backend-agnostic framework for building complex
multi-agent LLM systems. It separates configuration from execution using
structured manifests that define agents, tools, pipelines, workflow graphs,
memory, modes, and plugins. The engine does not perform raw LLM calls itself;
instead, it handles all higher-order orchestration: task creation, schema-safe
prompting, tool execution, memory retrieval, context assembly, routing, event
generation, and workflow transitions.

A Task acts as the stateful core of execution, carrying all information needed
as it moves through a pipeline. Pipelines represent explicit traversals through
a directed acyclic workflow graph, while the router selects the best pipeline
and agent assignments based on project rules, capabilities, user modes, and
plugin overrides. Each stage executes deterministically through a fixed
lifecycle of input preparation, agent or tool execution, and output handling.

Memory is layered and unified. The engine retrieves context from conversational
history, long-term RAG documents, agent state, user profiles, and
environment/tool outputs. All of this is merged into a coherent context package
before each agent call. A strict JSON engine ensures schema compliance,
retries, and repair, making structured outputs reliable. Every significant
action sends events through the telemetry bus, enabling logging, audits,
analytics, scoring, and evolution.

In total, the Agent Engine provides a clean foundation for any LLM application—
from simple assistant flows to deeply coordinated multi-agent ecosystems.
Developers define behavior through manifests and plugins, while the engine
ensures safety, determinism, extensibility, and predictable execution.
