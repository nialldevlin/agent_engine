# LLM NOTICE: Do not modify this file unless explicitly instructed by the user.

# **AGENT_ENGINE_OVERVIEW.md**

*Canonical Architecture Overview for Agent Engine*

---

## **0. Introduction**

Agent Engine was created to make it easy for anyone to build custom LLM-powered agent applications without giving up the advanced features found in commercial agent suites like ChatGPT, Claude Code, or Codex. Instead of forcing developers to wire together raw model calls and hope the results behave predictably, Agent Engine handles the hard parts: structuring workflows, validating outputs, managing context, routing through complex logic, coordinating parallel agents, and keeping detailed execution records. The goal is to provide the reliability, safety, and power of a professional-grade agent framework while allowing complete freedom to design any agent behavior, tool usage, or workflow pattern a project needs.

Agent Engine is a configuration-first orchestration framework for executing structured workflows that combine deterministic logic and large-language-model (LLM) agents. Instead of embedding workflow logic directly into code, projects specify behavior declaratively through manifests describing nodes, edges, context visibility, tool access, schemas, and execution policies. The engine consumes these manifests and executes the resulting workflow as a directed acyclic graph (DAG).

The system is designed around determinism, transparency, and extensibility. Every step of execution is logged, validated, and structured, allowing developers to reason about workflow behavior with clarity and precision. Nodes produce fully validated output, tasks retain complete histories, and the engine routes execution strictly according to the DAG. No hidden heuristics or implicit logic exists inside the runtime.

Agent Engine emphasizes strong separation between project-defined workflow logic and the engine’s stable execution semantics. The engine provides routing, validation, task management, parallelism, subtask tracking, and observability, while projects provide node logic, schemas, context profiles, and tool choices.

For underlying architectural motivations and research notes, see **docs/canonical/RESEARCH.md**.

---

## **1. Core Concepts**

---

### **1.1 Tasks**

A Task is the fundamental unit of work processed by Agent Engine. Every user request becomes a Task, which flows through the workflow DAG until it reaches an exit node. Tasks represent both the evolving state of execution and the authoritative source of truth for all data produced during the workflow.

A Task contains structured fields:

* an identifier
* the normalized input payload
* the current output produced by the most recent node
* a complete execution history organized by node
* standardized metadata describing routing decisions, lineage, and status
* references to task, project, and global memory layers

Task history stores every structured input and output a node sees or produces, along with the node’s status, tool calls, validation outcomes, and timestamps.

Tasks may produce descendants through two mechanisms:

* **clones**, created by Branch nodes
* **subtasks**, created by Split nodes

All clones and subtasks retain references to their parent Task, allowing the engine to track lineage, aggregate results, and determine when the parent Task has completed.

Parent Task completion follows strict rules:

* For clones, the parent may complete when one clone reaches an exit node, unless a merge later recombines clones for continued processing.
* For subtasks, the parent completes only once all subtasks have reached their exit conditions, unless a merge node recombines them earlier.

Task status uses a universal, standardized model: `success`, `failure`, or `partial`. Node status, tool status, and task status all use the same representation for consistency.

---

### **1.2 Operations (Nodes / Stages)**

Operations, also called nodes or stages, are atomic processing units within the DAG. Each node transforms a Task in an isolated, deterministic way using its context, configuration, and optional tools. Every node execution is recorded in the Task history.

Every node has exactly two defining dimensions:

**Kind** (node computation type):
* **agent nodes**, which invoke an LLM and validate its output against a schema
* **deterministic nodes**, which execute predefined logic without any LLM involvement

**Role** (node position and routing semantics):
* start, linear, decision, branch, split, merge, exit (defined in section 1.3 below)

These two dimensions form a cross-product: any valid combination of kind and role may exist (subject to node role constraints).

Regardless of kind, all nodes operate with structured input, produce schema-validated structured output, and emit a stage-level status according to the universal status model. Nodes may call tools if the node configuration allows them.

Node executions always occur with an assembled context determined by the node’s context profile, ensuring that each node sees exactly the information intended by the workflow’s design.

---

### **1.3 Node Roles (Execution Semantics)**

Every node has exactly one role, which defines how it interacts with the DAG and how the router moves execution forward. Roles describe execution semantics rather than behavioral logic, and they determine the number of inbound and outbound edges a node may have.

#### **Start**

Start nodes prepare the user’s raw input into a normalized Task input structure. They are deterministic-only, accept zero inbound edges, and produce one outbound edge. Multiple start nodes may exist, but one must be marked default so execution can begin deterministically when no explicit start node is provided.

#### **Linear**

Linear nodes represent the general case of Task transformation. They accept one inbound edge and produce one outbound edge. These nodes may be agent nodes or deterministic nodes and reflect the simplest form of progression through the graph.

#### **Decision**

Decision nodes select exactly one of multiple possible outbound edges. They have one inbound edge and two or more outbound edges. Each decision node outputs a structured, schema-validated selection that identifies the chosen edge while also producing the usual node output payload. If a decision node selects an edge that does not exist, the stage fails.

#### **Branch**

Branch nodes create parallel clones of the current Task. They have one inbound edge and two or more outbound edges. Each outbound edge receives a cloned Task, allowing parallel evaluation of the same content. The parent Task is considered complete when one clone successfully reaches an exit node, unless a merge node later recombines clone results for further processing.

#### **Split**

Split nodes create subtasks for hierarchical processing. They have one inbound edge and one or more outbound edges. Each outbound edge produces a new subtask derived from the parent. The parent Task ordinarily waits for all subtasks to complete unless a merge node recombines them earlier.

#### **Merge**

Merge nodes reconcile multiple upstream results. They have two or more inbound edges and exactly one outbound edge. Merge nodes wait for all incoming branches or subtasks to complete, receiving only successful outputs in a structured list that includes the output, the producing node ID, and associated metadata. Merge nodes may still observe failure metadata for diagnostic or selection purposes. Merge behavior, including how to combine or choose results, is defined per node.

Merge nodes may also recombine clones or subtasks back into the original Task, allowing further continuation along the DAG.

#### **Exit**

Exit nodes finalize Tasks. They are deterministic, accept one or more inbound edges, and produce no outbound edges. Exit nodes are restricted to read-only behavior: they do not modify Task state except to format and return the final output. They never call agents. Exit nodes read the standardized status already written into Task metadata by earlier stages and present this result to the user. Some exit nodes may carry an `always_fail` flag to produce structured error outputs.

---

### **1.4 Tools**

Tools are deterministic helpers invoked within node operations. They are not nodes themselves and are never part of the DAG. Instead, tools extend the capability of deterministic and agent nodes in a controlled, permission-regulated manner.

Tools report status using the universal status model. When a tool reports failure due to improper usage, the node receiving that failure typically inherits a failure status. Tools may also throw errors unrelated to misuse; such errors do not necessarily cause node failure, though they are recorded in the Task history.

Tool usage is defined in node configuration and is always logged.

---

### **1.5 Context & Memory**

Nodes execute within a structured, read-only context assembled for each stage. The context is derived from three memory layers:

* global memory
* project memory
* task memory

Each node must specify exactly one of the following:

* a context profile
* global context
* no context

This requirement ensures clear, predictable visibility of information during execution.

The **Context Assembler** runs before each node, producing a validated, structured context package. Nodes receive only what is defined by their context profile, ensuring determinism and preventing accidental visibility of information.

---

## **2. Workflow Graph (DAG)**

---

### **2.1 DAG Structure**

Agent Engine executes exactly one DAG per project. Each project config directory contains exactly one workflow DAG (workflow.yaml) that governs all routing for that project. The DAG may contain disconnected components, provided each component contains at least one start node and at least one exit node. The DAG must be acyclic and must always terminate.

Agent Engine does not support loops, cycles, or stage retries. Any iterative or retry behavior must be implemented externally or through future loop-like node mechanisms.

The DAG is the sole routing structure. No alternative routing system exists. There are no pipeline configuration files; all routing decisions must be represented as nodes and edges in the DAG.

---

### **2.2 Edges**

Edges are explicitly defined as `(from_node, to_node)` pairs. The DAG expresses all routing. Node roles determine how many edges are allowed and how execution proceeds. No pipeline configurations or external routing strategies exist; pipelines are emergent execution traces produced when the Task moves through the graph.

---

### **2.3 Node Identity & Reuse**

Node IDs must be globally unique. A node configuration describes exactly one behavior. Reusing the same node ID across multiple locations in the DAG is permitted; each occurrence acts as an independent stage and produces its own execution history entries while sharing the same configuration.

---

### **2.4 Branch / Split / Merge Semantics**

Branch, Split, and Merge provide structured parallelism and hierarchical decomposition.

**Branch nodes** create clones of the parent Task for parallel evaluation. Clones permit pipelines such as multi-agent voting, redundant processing, or expert selection.

**Split nodes** create subtasks to support hierarchical workflows. Subtasks may perform distinct components of a larger problem.

**Merge nodes** recombine clone or subtask results. Merges may continue with the resultant Task or finalize sub-results. All successful upstream outputs are included in the merge input, and failed branches or subtasks are excluded but logged. Merge nodes can be configured to halt or continue on failure, depending on workflow design.

---

## **3. Execution Model**

---

### **3.1 Stage Lifecycle**

Each stage execution follows this lifecycle:

* assemble context according to the node’s profile
* execute the node’s operation
* validate output against the node’s schema
* update Task state, including current output and history
* determine next routing via node role semantics

This lifecycle ensures deterministic, observable, structured computation.

---

### **3.2 Router**

The router drives DAG traversal. It selects the start node (either explicit or default) and follows node role semantics to determine subsequent stages. Router responsibilities include:

* linear progression through Linear nodes
* selecting outbound edges according to Decision node output
* creating clones for Branch nodes
* creating subtasks for Split nodes
* coordinating Merge nodes until all required inputs arrive
* halting execution at Exit nodes

The router does not supplement or modify DAG logic. It never infers routes outside the graph.

---

### **3.3 Concurrency & Parallelism**

Branch nodes and Split nodes generate concurrent execution paths. Merged execution resumes only when upstream clones or subtasks finish or are recombined. Parent Task behavior during parallelism follows strict rules:

* clones progress independently
* subtasks represent separate workflow paths
* parent progression depends on merge or exit behavior

Concurrency is predictable and explicit.

---

### **3.4 Status Determination**

All components—including nodes, tools, clones, subtasks, and the Task itself—use the standardized status model (`success`, `failure`, `partial`). Status must be set prior to reaching an exit node. Exit nodes do not determine correctness; they simply read the status and produce user-facing results.

---

## **4. Configuration & Manifest Structure**

---

### **4.1 Node Configuration**

Each node is defined exclusively by its manifest entry. Configuration includes:

* node kind (agent or deterministic)
* node role
* input and output schemas
* context profile
* allowed tools
* merge/branch/split strategy
* descriptive metadata

Manifests represent the complete public API for defining node behavior.

---

### **4.2 DAG Configuration**

A project’s manifest includes:

* definitions of all nodes
* a complete set of edges
* start nodes (one marked default)
* exit nodes, optionally with `always_fail`

This configuration defines the full workflow.

---

### **4.3 Failure Handling Configuration**

Nodes may specify whether execution should stop or continue when failures occur. Merge nodes may ignore failures, incorporate failure metadata, or cause overall failure depending on configuration. Error exit nodes provide structured representation of irrecoverable errors.

---

### **4.4 Task-Level Settings**

Projects may configure:

* memory usage policies
* status evaluation mechanisms
* history retention
* failure-handling strategies

Task-level behavior is always declared explicitly through manifest configuration.

---

## **5. Observability & Telemetry**

---

### **5.1 Execution Trace**

The execution trace is a complete record of the Task’s journey through the DAG. Each entry contains structured node inputs, outputs, statuses, tool invocations, and timestamps. Routing decisions, clone creation, subtask creation, and merges are all recorded.

### **5.2 Logs & Metrics**

Structured logging captures validation failures, context assembly, tool execution, LLM usage, and node performance. Metrics may include timing, resource usage, and parallel execution characteristics.

### **5.3 Replayability**

Deterministic nodes and structured output schemas allow workflows to be replayed for debugging, with nondeterministic LLM behavior constrained by strict schemas and historical records.

---

## **6. Error Handling**

---

### **6.1 Stage Errors**

Stages may fail due to schema mismatches, tool misuse, operation errors, or environment issues. Stage failure is recorded in the Task history with structured metadata. Nodes may be configured to treat stage failure as catastrophic or recoverable.

### **6.2 Task Errors**

Task-level errors arise from unrecoverable stage errors, explicit failure routing, invalid decisions, or reaching exit nodes marked `always_fail`. Parent tasks may enter a `partial` state when subtasks or components fail.

### **6.3 Error Exit Nodes**

Error exit nodes finalize Tasks with standardized failure information, structured output, and consistent semantics. They do not execute LLMs and maintain strict read-only behavior.

---

## **7. Example Execution Walkthrough**

A typical execution begins when a user request arrives. The engine selects the default or explicitly provided start node, which normalizes the input. Linear and decision stages process and route the Task forward. Branch nodes may create clones for parallel evaluation, and split nodes may create subtasks for hierarchical decomposition. Merge nodes reconcile the results and advance the Task. When the Task reaches an exit node, the exit node reads its status and presents a final structured response to the user. Every step of this process is captured in the Task history and execution trace.

---

## **8. Supporting Subsystems**

Agent Engine ships with a set of auxiliary subsystems that support auditability, observability, governance, and extensibility without altering the canonical DAG semantics described above.

### **8.1 Artifact & Output Storage Subsystem**

Every Task automatically materializes its validated outputs, tool artifacts, and telemetry snapshots into an artifact store. The subsystem indexes artifacts by task ID, node ID, and execution timestamp, allowing projects to retrieve the same structured data deterministically—whether for debugging, auditing, or feed-back into evaluations.

### **8.2 Engine Metadata & Versioning**

The engine maintains immutable metadata for every run, including engine version, manifest hashes, schema revisions, and adapter fingerprints. Metadata accompanies task history and artifacts so downstream tooling can verify that a given DAG execution used the expected manifest snapshot and runtime components.

### **8.3 Evaluation & Regression System**

Projects declare evaluation harnesses that replay canonical Tasks with known inputs, verify outputs against golden data, and record pass/fail status in the artifact store. Regression suites run deterministically using the same DAG, context profiles, and tool permissions, delivering reproducible confidence metrics before new code paths go live.

### **8.4 Performance Profiling & Metrics Layer**

Profiling collects timing, resource, and concurrency metrics per node, per tool invocation, and per Task. These signals stream through the telemetry bus for dashboards and alerting, helping operators ensure the engine meets SLAs without changing routing behavior or schemas.

### **8.5 Security & Policy Layer**

A dedicated policy evaluator monitors tool use, context visibility, and execution scopes for every node. Policies express constraints on data sources, tool permissions, and agent affordances so that deterministic semantics and DAG routing remain intact while enforcing project-specific security requirements.

### **8.6 Provider & Adapter Management Layer**

LLM providers, tool handlers, and other adapters register through a central provider registry. The management layer tracks adapter versions, credentials, and health and surfaces them to nodes that request them via manifests. Projects can swap providers without touching the DAG or node logic.

### **8.7 Debugger / Inspector Mode**

An inspector mode builds on the structured execution trace, allowing operators to pause, step, or replay individual nodes and view context payloads without mutating Tasks. It reuses telemetry and artifact information to remain fully deterministic and replayable.

### **8.8 Multi-Task Execution Model**

Agent Engine supports multiple Tasks running concurrently within a single process or across distributed workers, each with isolated history, memory, and artifact state. The multisession scheduler coordinates these Tasks without introducing hidden DAG routing or implicit synchronization.

### **8.9 CLI Framework**

The shared CLI (located under `src/agent_engine/cli/`) exposes a reusable REPL for interacting with any Agent Engine project. It supports profiles, prompt editing, command registries, file attachments, telemetry surfacing, and engine overrides while still funneling every user interaction through `Engine.run()` so the underlying DAG semantics remain canonical.

### **8.10 Persistent Memory & Artifact Storage**

Persistent task, project, and global memory layers keep their state on durable stores (file-backed, SQLite, or other append-only logs) configured via `memory.yaml`. The subsystem complements artifact storage by ensuring every Task’s historic outputs, tool results, and attached memory snapshots remain addressable for audits, replays, and evaluations without altering DAG routing semantics.

### **8.11 Secrets & Provider Credential Management**

Secret loaders and provider credential handlers wrap adapters to deliver encrypted credentials, API keys, or bearer tokens. Declarative manifests map secrets to providers, and the runtime injects them through the adapter registry while enforcing the existing node/tool permissions and routing constraints.

### **8.12 Multi-Task Execution Layer**

A cooperative scheduler orchestrates multiple concurrently running Tasks, each with isolated history, memory, artifacts, and telemetry. Optional queue-based scheduling and throttling keep execution deterministic and scoped per Task without introducing new DAG behaviors.

### **8.13 Packaging & Deployment Templates**

Reusable deployment templates describe the recommended directory structure, manifest versioning, environment bootstrapping, and reproducible packaging steps. Teams can copy these templates to standardize how Agent Engine projects are deployed while the engine itself remains unchanged.

---

## **9. Design Principles**

Agent Engine adheres to principles of declarative configuration, strict validation, strong separation of concerns, transparent execution, and deterministic routing through the DAG. The engine avoids implicit logic and instead relies solely on manifests to define behavior. Parallelism, context visibility, status propagation, and termination semantics are always explicit.

See **docs/canonical/RESEARCH.md** for additional conceptual background and rationale.

---

## **10. Glossary**

* **Task** — A unit of work flowing through the DAG.
* **Clone** — A parallel copy of a Task created by a Branch node.
* **Subtask** — A hierarchical child task created by a Split node.
* **Node / Stage** — An atomic operation applied to a Task.
* **Role** — The execution semantics governing a node’s position in the DAG.
* **Context** — Structured, read-only data assembled for a node according to its profile.
* **Tool** — A deterministic helper invoked within a node.
* **Branch / Split / Merge** — Mechanisms for structured parallelism and recombination.
* **Exit node** — A deterministic read-only finalizer for Task output.
* **Router** — Component responsible for following DAG semantics and node outputs.
* **Pipeline** — The actual execution trace a Task takes through the DAG.
* **Status model** — Standardized status values: `success`, `failure`, `partial`.
