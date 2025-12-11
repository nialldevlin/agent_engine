# AGENT_ENGINE_SPEC.md  
_Canonical Engine Specification | Matches AGENT_ENGINE_OVERVIEW_

## 0. Purpose & Scope

This document defines the **complete technical specification** for Agent Engine.  
It describes the internal subsystems, execution semantics, routing behavior, task model, status propagation rules, and validation requirements that all implementations of Agent Engine must satisfy.  

The **AGENT_ENGINE_OVERVIEW.md** describes *what* the engine is.  
This specification describes *how it must behave*.

This document is authoritative for engine correctness, determinism, and compatibility.

---

## 1. Architectural Responsibilities of Agent Engine

Agent Engine provides:

- Execution of declaratively defined workflows (DAGs) composed of deterministic and agent-driven operations.
- Routing, context assembly, task lifecycle management, and output validation.
- Enforcement of schemas, node roles, context profiles, and tool permissions.
- Parallelism through branch and split semantics.
- Deterministic merge behavior for recombining clones and subtasks.
- Structured error handling and standardized status propagation.
- Complete observability through task history and telemetry.

Agent Engine is **not** responsible for defining project workflows, schemas, models, or tools.  
These are always supplied by external project configuration.

---

## 2. Core Engine Data Structures

### 2.1 Task

A Task is the atomic unit of computation and contains:

- Unique task identifier
- Normalized input payload
- Current output (from most recently executed node)
- Full node-by-node execution history
- Standardized metadata:
  - status (`success`, `failure`, or `partial`)
  - lineage (parent, clone type, subtask type)
  - routing decisions
  - timestamps
- References to task-level, project-level, and global memory

Tasks may spawn:

- **Clones**, created by Branch nodes  
- **Subtasks**, created by Split nodes  

Rules:

- Parent is complete when:
  - **clones** → one finishes successfully (unless merged later)
  - **subtasks** → all finish (unless merged earlier)
- Task history must preserve every input and output exactly as provided.
- All status fields must use the universal status model.

### 2.2 Node (Operation)

Nodes are immutable objects created from manifest configuration.  
Each node has:

- ID (globally unique)
- Kind: `agent` or `deterministic`
- Role: exactly one of  
  `start`, `linear`, `decision`, `branch`, `split`, `merge`, `exit`
- Input schema
- Output schema
- Context profile (or global / none)
- Allowed tools (optional)
- Failure-handling configuration (`continue_on_failure` or `fail_on_failure`)
- Role-specific metadata (e.g., merge behavior)

### 2.3 Edge

Directed pairs `(from_node, to_node)`.  
Edges define all routing.  
No implicit routing exists.

Constraints:

- DAG must be acyclic.
- All nodes reachable from at least one start node.
- Each start node must reach at least one exit node.

---

## 3. Execution Semantics

### 3.1 Router

The router is responsible for:

- Selecting the start node (default or explicitly provided)
- Advancing the Task along the DAG according to node roles
- Creating clones (branch) or subtasks (split)
- Waiting for inbound edges to complete (merge)
- Halting at exit nodes

Router **never** invents routes; the DAG is the sole routing structure.

### 3.2 Stage Lifecycle

For every node execution:

1. Assemble context (using context profile)
2. Execute deterministic logic or invoke LLM agent
3. Validate output using node’s output schema
4. Update task current output
5. Write complete structured history entry
6. Determine routing according to node role

### 3.3 Node Role Behavior (Formal Specification)

#### **Start**
- deterministic only
- 0 inbound edges, 1 outbound
- normalizes raw input

#### **Linear**
- 1 inbound, 1 outbound
- transforms task

#### **Decision**
- 1 inbound, ≥2 outbound edges
- must output a valid edge selection
- if selected edge does not exist → node failure

#### **Branch**
- 1 inbound, ≥2 outbound
- creates **clones**  
- parent completes when one clone succeeds (unless merged)

#### **Split**
- 1 inbound, ≥1 outbound
- creates **subtasks**
- parent completes when all subtasks succeed (unless merged)

#### **Merge**
- ≥2 inbound, 1 outbound
- waits for all inbound tasks
- receives structured list of upstream outputs
- must validate output according to its schema

#### **Exit**
- deterministic only
- ≥1 inbound, 0 outbound
- read-only
- cannot invoke agents or tools
- returns output to user, using task’s pre-set status
- may be flagged `always_fail`

### 3.4 Status Propagation

All entities use:  
`success` | `failure` | `partial`

Rules:

- Tools report status → node inherits if misuse; errors not caused by misuse do not automatically change node status.
- Node status must be set explicitly.
- Merge nodes may ignore or consider failure metadata based on configuration.
- Task status must be set *before* reaching an exit node.
- Exit nodes never determine correctness; they only present already-decided status.

### 3.5 Failure Handling

Nodes may specify:

- `continue_on_failure: true`  
- `fail_on_failure: true` (default)

Branch, split, and merge nodes may incorporate failure logic defined per node.

---

## 4. Context & Memory Semantics

Each node must specify one of:

- context profile
- global context
- no context

The Context Assembler:

- retrieves memory from task / project / global layers
- applies retrieval and token policies (e.g., recency, hybrid)
- produces structured, read-only context

---

## 5. Tools (Deterministic Helpers)

Tools are not nodes.  
They may perform deterministic operations such as:

- file I/O  
- data transforms  
- command execution (sandboxed)  

Rules:

- Tools report status via the universal status model.
- Tools may throw implementation-level errors that do not necessarily fail the node.
- Tools are invoked only when the node lists them explicitly.
- Tools must comply with configured permissions (filesystem root, allow_network, etc.).

---

## 6. Observability Requirements

The engine must capture:

- every node input/output pair
- context used at each stage
- tool invocations
- routing decisions
- merge events
- clone/subtask creation
- timestamps
- structured status metadata

The engine must support:

- replayability
- deterministic debug traces
- optional telemetry sinks (plugins)

---

## 7. Error Semantics

### 7.1 Stage Errors
A stage may fail due to:

- schema mismatch  
- invalid routing decision  
- context assembly failure  
- tool misuse  

### 7.2 Task Errors
A task enters `partial` when some subtasks or clones fail but parent rules allow partial completion.

### 7.3 Exit Errors
Exit nodes marked `always_fail` override any existing success.

---

## 8. Engine Initialization Requirements

`Engine.from_config_dir(path)` must:

1. Load all manifests
2. Validate schemas and references
3. Construct node objects, edge table, and DAG
4. Validate DAG invariants
5. Initialize memory stores
6. Register tools and adapters
7. Load plugins
8. Return constructed engine

---

## 9. Completion Criteria (Engine Definition of Done)

Agent Engine is complete when:

- DAG execution matches formal semantics
- Node role behavior is correct
- Context assembly is correct
- Tools work with sandboxing + status reporting
- Router enforces all routing rules
- Parallel and hierarchical flows behave correctly
- Structured history logging is complete
- Exit node behavior is correct
- No hidden logic exists outside the DAG or manifests

---

## 10. Additional Operational Subsystems

### 10.1 Artifact & Output Storage Subsystem
Every Task collects validated outputs, tool results, and telemetry payloads into an artifact store indexed by task ID, node ID, schema, and timestamp, ensuring every execution is reproducible independent of the DAG logic.

### 10.2 Engine Metadata & Versioning
Every run generates immutable metadata describing engine version, manifest hashes, schema revisions, and adapter fingerprints. Metadata accompanies task history so downstream tools can verify the exact combination of code and configuration used for any execution.

### 10.3 Evaluation & Regression System
Projects may declare evaluation rigs that rebuild canonical Task inputs, rerun them through the router, and compare outputs to golden data or assertions. Regression suites run deterministically with the same tool permissions and context profiles, and they record pass/fail status within the artifact store.

### 10.4 Performance Profiling & Metrics Layer
Profiling instrumentation records durations, resource usage, context sizes, and queue latencies per stage, tool invocation, and Task. Metrics stream through the telemetry bus without affecting routing, providing dashboards and alerts while preserving deterministic semantics.

### 10.5 Security & Policy Layer
A policy evaluator inspects each stage’s context, tool accesses, and execution scope against declarative policies. It enforces constraints by permitting or denying operations before node execution, logging denials in the structured history without altering DAG routes.

### 10.6 Provider & Adapter Management Layer
Provider adapters for LLMs, tools, and telemetry sinks register through a central registry that validates configuration, tracks version metadata, and routes requests from manifest-defined nodes to the appropriate backend without embedding provider logic in the DAG.

### 10.7 Debugger / Inspector Mode
An inspector mode reuses telemetry, history, and artifacts to step through Tasks, pause between nodes, and replay contexts. It observes execution without mutation, leveraging deterministic traces to guarantee reproducibility.

### 10.8 Multi-Task Execution Model
The engine orchestrates multiple concurrently active Tasks while keeping their histories, memory, telemetry, and artifacts isolated. Multitasking changes scheduling but never introduces cycles, shortcuts, or implicit routing beyond the declared DAG.

### 10.9 CLI Framework
A shared CLI layer interacts with the engine via `Engine.run()`, managing prompt editing, command registries, profile selection, file attachments, telemetry surfacing, and session state while ensuring every interaction maps back to a canonical Task execution.

### 10.10 Persistent Memory & Artifact Storage
Persistent memory stores (task/project/global) persist to durable backends (file-backed, SQLite, etc.) and expose declarative configuration via `memory.yaml`. The subsystem guarantees every task’s memory snapshot and each validated output/tool artifact is indexed deterministically for replay or auditing.

### 10.11 Secrets & Provider Credential Management
Secret loaders expose secure credential material (API keys, secrets, certificates) through provider interfaces. Providers declare credential requirements in configuration, and the runtime binds them via the adapter registry before any tool or agent invocation, logging metadata without altering canonical routing.

### 10.12 Multi-Task Execution Layer
A cooperative scheduler distributes work across multiple concurrently running Tasks while keeping history, memory, artifacts, and telemetry isolated per Task. Optional queue-based scheduling handles backpressure, but no new routes or implicit synchronization semantics are introduced beyond the DAG.

### 10.13 Packaging & Deployment Templates
Deployment metadata captures recommended directory layout, manifest/version fingerprints, environment bootstrap steps, and reproducible packaging guidance. Projects may use these templates to standardize deployments without touching the core prediction logic or DAG structure.

---

# END OF SPEC
