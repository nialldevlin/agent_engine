# PROJECT_INTEGRATION_SPEC.md  
_Canonical Integration Specification | For All External Projects_

## 0. Purpose

This document defines **how external projects interact with Agent Engine**.  
It specifies:

- Required configuration files  
- What each manifest must contain  
- Rules for defining nodes, tools, schemas, and DAGs  
- How to run the engine  
- What guarantees the engine provides  
- How tasks, tools, and agents behave from the project’s perspective  

Projects do not write workflow code—only manifests.  
Agent Engine executes those manifests according to the canonical semantics.

---

## 1. Integration Model

Projects integrate with the engine by providing:

1. **One workflow DAG** (`workflow.yaml`)
   Each project config directory contains exactly one workflow DAG that governs all routing for that project.
2. **Node definitions** (embedded in workflow manifest)
3. **Agent definitions** (`agents.yaml`)
4. **Tool definitions** (`tools.yaml`)
5. **Memory + context profiles** (`memory.yaml`)
6. **Schemas** (registered or inline)
7. **Optional plugins** (`plugins.yaml`)

The engine guarantees:

- deterministic workflow execution
- strict schema validation
- structured task history
- compliant context assembly
- correct parallel/subtask semantics  

---

## 2. Required Manifest Set

A well-formed project directory:

```
project/
└── configs/
    ├── workflow.yaml
    ├── agents.yaml
    ├── tools.yaml
    ├── memory.yaml
    ├── schemas/
    └── plugins.yaml   (optional)
```

Projects must define **exactly one DAG**.

---

## 3. Manifest Specifications

### 3.1 workflow.yaml (DAG Definition)

Defines:

- nodes
- edges
- start nodes (≥1, one marked default)
- exit nodes (≥1; may include error exit nodes)

**Important**: There are no pipeline configuration files. All routing decisions must be represented as nodes and edges in the DAG. Pipelines are emergent execution traces that result from a Task flowing through the graph.

#### Node fields:

| Field | Description |
|-------|-------------|
| `id` | Globally unique node ID |
| `kind` | `"agent"` or `"deterministic"` |
| `role` | one of: `start`, `linear`, `decision`, `branch`, `split`, `merge`, `exit` |
| `schema_in` | input schema reference |
| `schema_out` | output schema reference |
| `context` | context profile OR `global` OR `none` |
| `tools` | optional list of allowed tools |
| `continue_on_failure` | bool (default false) |
| Role-specific config | merge behavior, etc. |

**Kind and Role Cross-Product**: Any valid combination of `kind` ∈ {`agent`, `deterministic`} and `role` ∈ {`start`, `linear`, `decision`, `branch`, `split`, `merge`, `exit`} may exist, subject to the constraints below.

#### Edge fields:

| Field | Description |
|-------|-------------|
| `from` | node id |
| `to` | node id |
| `label` | optional label for decision nodes |

Constraints:

- Graph must be acyclic
- Merges must have ≥2 inbound
- Starts have 0 inbound
- Exits have 0 outbound
- Branch must have ≥2 outbound
- Split must have ≥1 outbound
- Decision must have ≥2 outbound
- Linear exactly 1 inbound + 1 outbound

No cycles; no retries built in; loops must be implemented outside the DAG.

---

### 3.2 agents.yaml

Defines agent nodes:

| Field | Description |
|-------|-------------|
| `model` | LLM identifier |
| `schema_out` | schema name |
| `context` | context profile |
| `tools` | allowed tools |

Agents must produce output conforming to declared `schema_out`.

---

### 3.3 tools.yaml

Defines deterministic tools external projects may use:

| Field | Description |
|-------|-------------|
| `type` | tool handler type |
| `root` | optional filesystem restriction |
| `allow_network` | bool |
| `allow_shell` | bool |

Tool status affects node status only when caused by misuse.

---

### 3.4 memory.yaml

Defines memory stores:

- `task_store`
- `project_store`
- `global_store` (optional)

Defines **context profiles** specifying:

- retrieval policy  
- memory sources  
- token budget  

Each node must reference exactly one of:

- context profile
- global context
- no context

---

### 3.5 schemas/

Schema files define JSON structures expected for inputs and outputs.  
Engine validates strictly.

---

### 3.6 plugins.yaml (Optional)

Plugins are read-only observers on events (telemetry, logging, metrics). They receive access to task lifecycle events, node execution events, routing decisions, and errors, but cannot modify workflow behavior or DAG structure.

Plugins are configured via `plugins.yaml` and function purely as observability hooks.

---

## 4. Project Responsibilities

A project must:

1. Provide valid manifests  
2. Ensure schemas reference valid definitions  
3. Supply correct model names to supported LLM adapters  
4. Implement custom tools if referenced  
5. Provide a top-level input for the start node  
6. Handle results returned by exit nodes  

---

## 5. Engine Guarantees to Projects

Agent Engine guarantees:

- Valid manifests → deterministic DAG execution  
- Invalid manifests → structured errors at load time  
- No hidden behavior, no inferred routing  
- Parallel semantics exactly as defined  
- Merge semantics exactly as configured  
- No LLM invocation inside exit nodes  
- Schemas strictly enforced  
- Reproducible execution traces  

## 6. Extended Feature Manifests

Beyond the core manifests, projects may opt into additional configuration files to enable the new subsystems without modifying DAG semantics.

### 6.1 artifacts.yaml (Artifact & Output Storage)

Defines storage bindings for task outputs, tool artifacts, and telemetry snapshots. Each entry names an artifact bucket, retention policy, and indexing rules so the engine can persist validated results alongside task history.

### 6.2 engine_metadata.yaml (Metadata & Versioning)

Declares engine version tags, manifest SHA fingerprints, schema revisions, and provider adapter versions. The engine records this metadata for every load and exposes it through telemetry and artifacts.

### 6.3 evaluations.yaml (Evaluation & Regression)

Describes deterministic evaluation rigs and regression suites: input payloads, expected schema outputs, and pass/fail assertions. These evaluations run through the same DAG and tool permissions and write results to the artifact store.

### 6.4 metrics.yaml (Performance Profiling & Metrics)

Controls which stages, tools, and telemetry sinks emit profiling data. Projects can toggle timers, resource counters, and queue metrics so operators can monitor performance without changing routing rules.

### 6.5 policy.yaml (Security & Policy Layer)

Specifies declarative policies that restrict tool access, context visibility, and execution scope per node or project. The engine evaluates these policies before each stage; violations are logged but do not alter the DAG.

### 6.6 providers.yaml (Provider & Adapter Management)

Lists LLM providers, tool backends, telemetry endpoints, credentials, and adapter configuration. Nodes reference these adapters through manifest fields, allowing the registry to resolve providers without modifying node logic.

### 6.7 inspector.yaml (Debugger / Inspector Mode)

Enables inspector hooks, including allowed telemetry events, pause checkpoints, and replay policies. Inspector mode reads artifacts and history to step through Tasks without introducing side effects.

### 6.8 execution.yaml (Multi-Task Execution Model)

Configures Task concurrency limits, session isolation policies, and scheduling hints. The engine uses these directives to run multiple Tasks concurrently while preserving history, memory, and artifact isolation.

### 6.9 cli_profiles.yaml (CLI Framework)

Describes CLI profiles—custom commands, input-to-`Engine.run()` mappings, presentation rules, default `config_dir`, and telemetry overlays. Profiles allow the shared CLI shell to serve multiple Agent Engine apps without altering the runtime.

### 6.10 persistent_memory.yaml (Persistent Memory)

Specifies durable stores for task/project/global memory, including file-backed, SQLite, or append-only log targets. Projects declare retention policies, serialization formats, and context visibility rules so the engine can reload memory without mutating DAG semantics.

### 6.11 provider_credentials.yaml (Secrets & Providers)

Lists encrypted secrets, credential references, and provider bindings. Each entry indicates which adapter consumes the credential, the expected type (API key, certificate, OAuth token), and optional rotation metadata. The engine resolves credentials through the adapter registry before agent/tool execution.

### 6.12 scheduler.yaml (Multi-Task Execution)

Configures cooperative scheduling policies, queue-based execution parameters, concurrency limits, and Task isolation hints. These directives allow multiple Tasks to run concurrently while keeping history, memory, and artifacts segregated according to PROJECT_INTEGRATION_SPEC §6.10.

### 6.13 deployment.yaml (Packaging & Deployment)

Captures recommended directory layout, manifest version tags, environment bootstrap commands, and reproducible deployment checklists. This metadata helps teams align on packaging and runtime expectations without touching canonical DAG behavior.
---

## 7. Running the Engine

Project code typically looks like:

```python
from agent_engine import Engine

engine = Engine.from_config_dir("./configs")

result = engine.run(user_input)
print(result.output)
```

The return object includes:

- final structured output from exit node
- task status
- complete task history (optional inspectable)

---

## 8. Example Project Layout

```
my_agent_app/
├── configs/
│   ├── workflow.yaml
│   ├── agents.yaml
│   ├── tools.yaml
│   ├── memory.yaml
│   ├── schemas/
│   └── plugins.yaml
├── src/
│   └── main.py
└── README.md
```

---

## 9. Compliance Requirements

A project is compliant when:

- manifests validate
- DAG satisfies all structural rules
- all referenced tools and agents exist
- schemas are valid
- exit nodes return only structured outputs

---

## 10. Versioning & Stability

This document is part of the canonical contract.  
Changes that modify required fields, node semantics, or DAG structure are **breaking changes**.

---

# END OF SPEC
