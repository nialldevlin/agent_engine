# Agent Engine Architecture

This document describes the complete architecture of Agent Engine, including the core data structures, execution model, routing semantics, and system design.

## Canonical References

The authoritative semantics for every subsystem live in the canonical documents:
- `docs/canonical/AGENT_ENGINE_SPEC.md` – behavioral contract and execution semantics
- `docs/canonical/AGENT_ENGINE_OVERVIEW.md` – architectural overview and motivations
- `docs/canonical/PROJECT_INTEGRATION_SPEC.md` – required manifests and integration rules

Use this architecture doc as an implementation map; consult the canonical files above for the source of truth.

## Table of Contents

1. [Core Concepts](#core-concepts)
2. [DAG Structure](#dag-structure)
3. [Node Lifecycle & State Transitions](#node-lifecycle--state-transitions)
4. [Routing Semantics](#routing-semantics)
5. [Task Lineage](#task-lineage)
6. [Plugin System & Telemetry](#plugin-system--telemetry)
7. [Memory & Context](#memory--context)
8. [Error Handling](#error-handling)

---

## Core Concepts

Agent Engine is a configuration-first orchestration framework that executes workflows as Directed Acyclic Graphs (DAGs). Key concepts:

- **Workflow**: A DAG defined in `workflow.yaml` with nodes and edges
- **Node**: An operation in the workflow (agent-driven or deterministic)
- **Task**: An execution instance of a workflow with input, output, and history
- **Role**: One of seven semantic node types (start, linear, decision, branch, split, merge, exit)
- **Context**: Assembled knowledge base provided to nodes during execution
- **Tool**: Deterministic function invoked by nodes (filesystem, HTTP, compute, etc.)
- **Agent**: LLM-driven operation that can use tools and context

---

## DAG Structure

The DAG is the core execution model. Here's how nodes and edges are organized:

```mermaid
graph LR
    subgraph Workflow["Workflow Structure"]
        direction LR
        S["START<br/>Role: start"]
        L1["Linear Operation<br/>Role: linear"]
        D["Decision<br/>Role: decision"]
        B["Branch<br/>Role: branch"]
        SP["Split<br/>Role: split"]
        M["Merge<br/>Role: merge"]
        E["EXIT<br/>Role: exit"]

        S -->|Edge| L1
        L1 -->|Edge| D
        D -->|yes| B
        D -->|no| SP
        B -->|Clone A| M
        B -->|Clone B| M
        SP -->|Subtask 1| M
        SP -->|Subtask 2| M
        M -->|Merged| E
    end

    subgraph Properties["Node Properties"]
        ID["ID<br/>Unique identifier"]
        Kind["Kind<br/>agent or deterministic"]
        Role["Role<br/>One of seven types"]
        Context["Context<br/>Profile or global"]
        Tools["Tools<br/>Allowed tool IDs"]
        Failure["Failure Policy<br/>continue or fail"]
    end

    Workflow -.->|has| Properties

    style S fill:#90EE90
    style E fill:#FFB6C6
    style D fill:#87CEEB
    style B fill:#FFD700
    style SP fill:#FFD700
    style M fill:#DDA0DD
```

### DAG Invariants

1. **Acyclic**: No cycles allowed; all paths must terminate
2. **Reachable**: Every node must be reachable from at least one START node
3. **Complete**: Every START node must have a path to at least one EXIT node
4. **Role Constraints**:
   - Exactly one START node (default_start=true)
   - Exactly one EXIT node
   - DECISION nodes have multiple outgoing edges with labels
   - BRANCH creates clones; SPLIT creates subtasks
   - MERGE has multiple incoming edges

---

## Node Lifecycle & State Transitions

Each node execution follows a strict lifecycle with defined state transitions:

```mermaid
stateDiagram-v2
    [*] --> Pending: Task arrives at node

    Pending --> ContextAssembly: Node kind != start
    Pending --> Validation: Node kind == start

    Validation --> InputValidation: Schema validation
    InputValidation --> Success_Valid: Valid input
    InputValidation --> Failed: Invalid input

    ContextAssembly --> ContextReady: Context assembled
    ContextAssembly --> Failed: Assembly failed

    ContextReady --> ToolInvocation: Deterministic node with tools
    ContextReady --> AgentExecution: Agent node
    ContextReady --> Routing: No tools/execution

    ToolInvocation --> OutputValidation: Tool completed
    AgentExecution --> OutputValidation: Agent completed
    Routing --> OutputValidation: Routing decided

    OutputValidation --> Success_Valid: Valid output
    OutputValidation --> PartialSuccess: Partial success (continue_on_failure)
    OutputValidation --> Failed: Invalid output

    Success_Valid --> DecisionRouting: Decision node
    Success_Valid --> NextNode: Other roles

    PartialSuccess --> NextNode
    Failed --> ErrorHandling: Check continue_on_failure

    ErrorHandling --> NextNode: continue_on_failure=true
    ErrorHandling --> [*]: continue_on_failure=false

    DecisionRouting --> NextNode: Route by decision
    NextNode --> [*]: Emit node_completed
    [*] --> [*]: Emit all events

    style Pending fill:#FFE4B5
    style ContextAssembly fill:#87CEEB
    style ToolInvocation fill:#98FB98
    style AgentExecution fill:#DDA0DD
    style DecisionRouting fill:#FFD700
    style Success_Valid fill:#90EE90
    style Failed fill:#FFB6C6
    style PartialSuccess fill:#FFFFE0
```

### State Details

- **Pending**: Node waiting for execution
- **Context Assembly**: Gathering context from memory stores
- **Validation**: Checking input/output against schemas
- **Tool Invocation**: Running deterministic tools
- **Agent Execution**: LLM generating output
- **Routing**: Decision node selecting next path
- **Success/Failed/Partial**: Terminal states for node execution

---

## Routing Semantics

The router implements seven distinct node roles, each with unique routing behavior:

```mermaid
graph LR
    subgraph Roles["Seven Node Roles & Routing"]
        direction LR

        subgraph START["START Role"]
            START_A["Always routes to<br/>next connected node<br/>Initializes task"]
        end

        subgraph LINEAR["LINEAR Role"]
            LINEAR_A["Sequential routing<br/>One input → one output<br/>No branching"]
        end

        subgraph DECISION["DECISION Role"]
            DECISION_A["Conditional routing<br/>Examines output<br/>Routes by edge labels<br/>One path selected"]
        end

        subgraph BRANCH["BRANCH Role"]
            BRANCH_A["Clone creation<br/>One task → multiple clones<br/>All clones execute<br/>independently<br/>Task completes when<br/>one finishes"]
        end

        subgraph SPLIT["SPLIT Role"]
            SPLIT_A["Subtask creation<br/>One task → multiple subtasks<br/>All subtasks execute<br/>in parallel<br/>Task waits for all<br/>to finish"]
        end

        subgraph MERGE["MERGE Role"]
            MERGE_A["Recombination<br/>Multiple inputs → one output<br/>Clones or subtasks join<br/>Aggregates results"]
        end

        subgraph EXIT["EXIT Role"]
            EXIT_A["Terminal node<br/>One input → workflow end<br/>Returns task output<br/>Emits task_completed"]
        end
    end

    style START_A fill:#90EE90
    style LINEAR_A fill:#87CEEB
    style DECISION_A fill:#FFD700
    style BRANCH_A fill:#FFA500
    style SPLIT_A fill:#FF6347
    style MERGE_A fill:#DDA0DD
    style EXIT_A fill:#FFB6C6
```

### Detailed Routing Rules

#### START Node
- Single outgoing edge to first processing node
- Initializes task context
- Always succeeds (input validation only)
- No failure handling

#### LINEAR Node
- Single input path, single output path
- Deterministic or agent-driven
- Can use tools and context
- Failure handling applies

#### DECISION Node
- Single input path
- Multiple outgoing edges with labels
- Output determines which edge to follow
- Routed by edge label matching output value
- Only one path selected

#### BRANCH Node
- Single input path
- Creates multiple independent clones
- Each clone executes the complete downstream DAG
- Parent task completes when any clone succeeds
- Clone lineage tracked for observability

#### SPLIT Node
- Single input path
- Creates multiple subtasks with shared parent
- All subtasks must complete
- Results aggregated at MERGE node
- Parent waits for all subtasks to finish

#### MERGE Node
- Multiple input paths (from clones or subtasks)
- Single output path
- Aggregates results from multiple sources
- Deterministic merge logic combines outputs
- Awaits all inputs before proceeding

#### EXIT Node
- Single input path
- Terminates workflow execution
- Returns final task output
- Emits task_completed event
- No further routing

---

## Task Lineage

Tasks can create children through branching and splitting. Lineage is tracked for observability and debuggability:

```mermaid
graph TD
    Parent["Parent Task<br/>task-parent-001"]

    Parent -->|BRANCH| Clone1["Clone 1<br/>Lineage: branch-clone"]
    Parent -->|BRANCH| Clone2["Clone 2<br/>Lineage: branch-clone"]
    Parent -->|BRANCH| Clone3["Clone 3<br/>Lineage: branch-clone"]

    Clone1 -->|executes| DAG1["Downstream DAG"]
    Clone2 -->|executes| DAG2["Downstream DAG"]
    Clone3 -->|executes| DAG3["Downstream DAG"]

    DAG1 -->|completes| Merge["MERGE Node<br/>Recombination"]
    DAG2 -->|completes| Merge
    DAG3 -->|completes| Merge

    Merge -->|aggregates| MergeOut["Merged Output"]

    Parent2["Parent Task<br/>task-parent-002"]
    Parent2 -->|SPLIT| Sub1["Subtask 1<br/>Lineage: split-subtask"]
    Parent2 -->|SPLIT| Sub2["Subtask 2<br/>Lineage: split-subtask"]
    Parent2 -->|SPLIT| Sub3["Subtask 3<br/>Lineage: split-subtask"]

    Sub1 -->|independent| SubDAG1["Subtask DAG"]
    Sub2 -->|independent| SubDAG2["Subtask DAG"]
    Sub3 -->|independent| SubDAG3["Subtask DAG"]

    SubDAG1 -->|finishes| SubMerge["Parallel Completion"]
    SubDAG2 -->|finishes| SubMerge
    SubDAG3 -->|finishes| SubMerge

    SubMerge -->|parent waits| SubMergeOut["Final Output"]

    subgraph BranchSection["BRANCH Pattern"]
        Parent
        Clone1
        Clone2
        Clone3
        DAG1
        DAG2
        DAG3
        Merge
        MergeOut
    end

    subgraph SplitSection["SPLIT Pattern"]
        Parent2
        Sub1
        Sub2
        Sub3
        SubDAG1
        SubDAG2
        SubDAG3
        SubMerge
        SubMergeOut
    end

    style Parent fill:#90EE90
    style Parent2 fill:#90EE90
    style Clone1 fill:#FFA500
    style Clone2 fill:#FFA500
    style Clone3 fill:#FFA500
    style Sub1 fill:#FF6347
    style Sub2 fill:#FF6347
    style Sub3 fill:#FF6347
    style Merge fill:#DDA0DD
    style SubMerge fill:#DDA0DD
```

### Lineage Metadata

Each task carries metadata about its lineage:

```python
{
  "task_id": "task-001",
  "parent_id": None,
  "lineage": {
    "type": None,  # "branch-clone" or "split-subtask"
    "parent_task_id": None,
    "node_id": None,  # Node that created this task
    "position": 0  # Position in clone/subtask list
  }
}
```

---

## Plugin System & Telemetry

The engine emits events throughout execution, which are observed by plugins:

```mermaid
graph LR
    subgraph Execution["Task Execution"]
        TaskStart["task_started"]
        NodeStart["node_started"]
        ContextAssm["context_assembled"]
        ToolInvoke["tool_invoked"]
        ToolComplete["tool_completed"]
        AgentExec["agent_execution"]
        NodeComplete["node_completed"]
        Routing["routing_decision"]
        TaskComplete["task_completed"]
    end

    subgraph LineageEvents["Lineage Events"]
        CloneCreate["clone_created"]
        SubtaskCreate["subtask_created"]
    end

    subgraph Events["Telemetry Event Stream"]
        EventBus["Event Bus"]
    end

    TaskStart -->|emit| EventBus
    NodeStart -->|emit| EventBus
    ContextAssm -->|emit| EventBus
    ToolInvoke -->|emit| EventBus
    ToolComplete -->|emit| EventBus
    AgentExec -->|emit| EventBus
    NodeComplete -->|emit| EventBus
    Routing -->|emit| EventBus
    TaskComplete -->|emit| EventBus
    CloneCreate -->|emit| EventBus
    SubtaskCreate -->|emit| EventBus

    EventBus -->|dispatch| Plugin1["Plugin 1<br/>on_event"]
    EventBus -->|dispatch| Plugin2["Plugin 2<br/>on_event"]
    EventBus -->|dispatch| Plugin3["Plugin N<br/>on_event"]

    Plugin1 -->|log| Sink1["Logging"]
    Plugin2 -->|metrics| Sink2["Metrics"]
    Plugin3 -->|trace| Sink3["Tracing"]

    style Execution fill:#E6F3FF
    style LineageEvents fill:#FFE6E6
    style EventBus fill:#90EE90
    style Plugin1 fill:#FFE4B5
    style Plugin2 fill:#FFE4B5
    style Plugin3 fill:#FFE4B5
```

### Event Types

The engine emits the following event categories:

1. **Task Events**: `task_started`, `task_completed`, `task_failed`
2. **Node Events**: `node_started`, `node_completed`, `node_failed`
3. **Tool Events**: `tool_invoked`, `tool_completed`, `tool_failed`
4. **Context Events**: `context_assembled`, `context_failed`
5. **Routing Events**: `routing_decision`, `routing_branch`, `routing_split`, `routing_merge`
6. **Lineage Events**: `clone_created`, `subtask_created`

### Plugin Flow

1. **Engine emits event** → Event object created with metadata
2. **Event Bus receives** → Event stored in event log
3. **Plugin dispatch** → Each registered plugin receives event copy
4. **Plugin processing** → Plugin observes without modifying
5. **Error isolation** → Plugin exceptions logged, don't affect execution

---

## Memory & Context

Memory stores hold knowledge that's assembled into context during node execution:

```mermaid
graph TB
    subgraph MemoryLayer["Memory Architecture"]
        TaskMem["Task Store<br/>Per-task isolated"]
        ProjectMem["Project Store<br/>Project-wide shared"]
        GlobalMem["Global Store<br/>Cross-project shared"]
    end

    subgraph ProfileLayer["Context Profiles"]
        Profile1["Profile: compact<br/>max_tokens: 2000<br/>retrieval: recency"]
        Profile2["Profile: standard<br/>max_tokens: 4000<br/>retrieval: hybrid"]
        Profile3["Profile: comprehensive<br/>max_tokens: 8000<br/>retrieval: semantic"]
    end

    subgraph AssemblyLayer["Context Assembly"]
        Retrieval["Retrieval Policy<br/>recency|semantic|hybrid"]
        Filtering["Token Filtering<br/>Respect max_tokens"]
        Ordering["Result Ordering<br/>Ranked by relevance"]
        Assembly["Final Context<br/>Ready for LLM"]
    end

    subgraph NodeExecution["Node Execution"]
        Agent["Agent Node<br/>Uses context +<br/>tools to respond"]
        Deterministic["Deterministic Node<br/>Uses context +<br/>logic to compute"]
    end

    TaskMem --> Profile1
    ProjectMem --> Profile2
    GlobalMem --> Profile3

    Profile1 --> Retrieval
    Profile2 --> Retrieval
    Profile3 --> Retrieval

    Retrieval --> Filtering
    Filtering --> Ordering
    Ordering --> Assembly

    Assembly --> Agent
    Assembly --> Deterministic

    style TaskMem fill:#87CEEB
    style ProjectMem fill:#DDA0DD
    style GlobalMem fill:#90EE90
    style Assembly fill:#FFD700
```

### Context Assembly Process

1. **Profile Lookup**: Determine which memory stores and policies apply
2. **Retrieval**: Query task/project/global stores using specified policy
3. **Filtering**: Remove items exceeding max_token budget
4. **Ordering**: Rank by recency, semantic similarity, or hybrid score
5. **Injection**: Provide assembled context to node execution

---

## Error Handling

Errors are handled at multiple levels with consistent status propagation:

```mermaid
graph TD
    NodeExec["Node Execution<br/>Starts"]

    NodeExec -->|success| Success["Output Valid"]
    NodeExec -->|error| ErrorCheck{"continue_on_failure?"}

    ErrorCheck -->|false| PropagateUp["Propagate Error<br/>task_failed"]
    ErrorCheck -->|true| PartialSuccess["Partial Success<br/>Task continues"]

    Success --> NextNode["Route to<br/>Next Node"]
    PartialSuccess --> NextNode

    NextNode -->|normal path| Continue["Continue Execution"]
    NextNode -->|decision| DecisionRoute["Route by<br/>Decision Output"]

    Continue --> MoreNodes{"More<br/>Nodes?"}
    DecisionRoute --> MoreNodes

    MoreNodes -->|yes| NodeExec
    MoreNodes -->|no| ExitNode["EXIT Node"]

    ExitNode --> TaskSuccess["task_completed<br/>status: success"]
    PropagateUp --> TaskFailed["task_completed<br/>status: failure"]

    style NodeExec fill:#87CEEB
    style Success fill:#90EE90
    style PartialSuccess fill:#FFFFE0
    style PropagateUp fill:#FFB6C6
    style TaskSuccess fill:#90EE90
    style TaskFailed fill:#FFB6C6
```

### Status Propagation Rules

1. **Node succeeds** → Output becomes task output
2. **Node fails, continue_on_failure=false** → Task fails immediately
3. **Node fails, continue_on_failure=true** → Task continues (partial status)
4. **All nodes execute** → Task reaches EXIT node
5. **EXIT node completes** → Task marked success/failure based on final status

---

## System Integration

### Configuration Files

```
project/
├── workflow.yaml          # DAG definition
├── agents.yaml           # LLM configurations
├── tools.yaml            # Tool definitions
├── memory.yaml           # Memory stores & profiles
├── plugins.yaml          # Plugin configurations
├── cli_profiles.yaml     # CLI behavior
└── schemas/              # Optional JSON schemas
```

### Runtime Components

```
Engine
├── DAG                    # Loaded workflow graph
├── Router                 # Routing logic (7 roles)
├── TaskManager            # Task lifecycle + lineage
├── ContextAssembler       # Memory assembly
├── ToolRegistry           # Tool lookup & invocation
├── AdapterRegistry        # LLM provider access
├── EventBus              # Telemetry distribution
├── PluginRegistry        # Plugin management
└── MemoryStores          # Task/project/global stores
```

### Execution Flow

1. **Initialization**: Load config, validate schemas, construct DAG
2. **Task Creation**: Create task from input, assign to start node
3. **Node Loop**: Execute nodes following DAG edges
4. **Context Assembly**: Prepare context for each node
5. **Execution**: Run deterministic tools or invoke LLM agent
6. **Routing**: Determine next node based on node role
7. **Event Dispatch**: Emit events to plugin registry
8. **Completion**: Reach EXIT node, return final task output

---

## Key Principles

1. **Deterministic**: Same input → same execution path + events
2. **Observable**: All operations emit telemetry
3. **Extensible**: Plugins observe without modifying
4. **Safe**: Error handling prevents cascading failures
5. **Traceable**: Full lineage preserved for debugging
6. **Configurable**: YAML-driven, no code changes needed
7. **Typed**: All inputs/outputs validated against schemas

This architecture provides a robust foundation for building complex AI-driven workflows with observability, error handling, and extensibility built in.
