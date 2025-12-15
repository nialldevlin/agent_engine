# Data Flow & Context in Agent Engine

Understanding how data moves through your workflows and how nodes access context.

## Table of Contents

1. [Overview](#overview)
2. [The Task Lifecycle](#the-task-lifecycle)
3. [Context & Memory Tiers](#context--memory-tiers)
4. [Tool Output Capture](#tool-output-capture)
5. [Linear Workflows](#linear-workflows)
6. [Decision Routing](#decision-routing)
7. [Advanced Patterns](#advanced-patterns)
8. [Debugging Data Flow](#debugging-data-flow)

---

## Overview

Every workflow execution is a **Task** that moves through your DAG. As the task progresses:

1. **Input** enters the first node
2. **Node processes** the input, optionally calling tools
3. **Output** becomes the **next node's input**
4. **Context** is assembled from multi-tier memory
5. **Process repeats** until reaching EXIT

### Key Concepts

- **Task**: Single execution of a workflow with an ID, history, and state
- **current_output**: The output from the last executed node
- **context**: Memory items available to the current node
- **ToolCallRecord**: Captured execution record of a tool call
- **StageExecutionRecord**: Complete record of a node's execution

---

## The Task Lifecycle

### Phase 1: Task Creation

```
Input: {"request": "analyze code"}
         ↓
Engine.run() → Task(id="task-123", input={...})
```

### Phase 2: Node Execution

Each node executes in sequence:

```
Task ──→ [START Node]
           ├─ Validate input
           ├─ Assemble context
           ├─ Execute (deterministic)
           └─ Update task.current_output
             ↓
        [PROCESS Node]
           ├─ Receive task.current_output as input
           ├─ Assemble context (can see previous outputs)
           ├─ Execute (call tools, LLM)
           ├─ Capture tool outputs
           └─ Update task.current_output
             ↓
        [EXIT Node]
           ├─ Receive final output
           └─ End task
             ↓
           Task Complete
```

### Complete Execution Example

```python
# Input
input_data = {"request": "find authentication code"}

# Task created with input
task = Task(id="task-123")
task.current_output = input_data

# After START node
output = start_node(input_data)
task.current_output = output  # Now contains normalized data

# After PROCESS node (with tools)
output = process_node(task.current_output)
# output = {"result": "found auth.py", "tool_calls": [...]}
task.current_output = output

# After EXIT node
final_output = exit_node(task.current_output)
# Task completes with final_output
```

---

## Context & Memory Tiers

Agent Engine has three memory tiers that persist across nodes:

### The Three Tiers

| Tier | Scope | Lifetime | When to Use |
|------|-------|----------|------------|
| **Task** | Current workflow run | Cleared on task completion | Temporary state within one execution |
| **Project** | Entire project | Persistent | Shared data across multiple runs |
| **Global** | Entire system | Persistent | System-wide knowledge |

### Visual Hierarchy

```
┌─────────────────────────────┐
│   GLOBAL Memory Store       │  Visible to all projects
│  (Long-lived, cross-project)│
├─────────────────────────────┤
│   PROJECT Memory Store      │  Visible within project
│ (Long-lived, project-scoped)│
├─────────────────────────────┤
│   TASK Memory Store         │  Visible in current run
│  (Ephemeral, task-scoped)   │
└─────────────────────────────┘
```

### Specifying Context Access

Each node specifies which tiers it can see:

```yaml
nodes:
  - id: "search"
    context: "none"     # Can't see any memory

  - id: "analyze"
    context: "global"   # Can see: task + project + global

  - id: "decide"
    context: "project"  # Can see: task + project (not global)
```

### How Context is Assembled

When a node executes, the engine:

1. **Collects** items from specified memory tiers
2. **Filters** by tags (if specified)
3. **Sorts** by recency
4. **Selects** within token budget
5. **Delivers** as ContextPackage to node

Example:

```python
# For a node with context="global"
context = {
    "task_items": [...],      # From TASK memory
    "project_items": [...],   # From PROJECT memory
    "global_items": [...]     # From GLOBAL memory
}

# Node receives all three and can reference any
agent_prompt = f"""
Here's what we know:
{context}

Your task: ...
"""
```

---

## Tool Output Capture

### What Happens When Tools Run

```
Node executes with tool_plan
       ↓
For each tool step:
  1. Execute tool
  2. Capture inputs & output
  3. Record as ToolCallRecord
  4. Validate against schema (if present)
       ↓
Collect all ToolCallRecords
       ↓
Attach to node output
       ↓
Node output becomes:
{
  "result": "...",
  "tool_calls": [
    {
      "call_id": "call-123",
      "tool_id": "search_codebase",
      "inputs": {"query": "auth"},
      "output": ["auth.py", "login.py"],
      "metadata": {...}
    }
  ]
}
```

### ToolCallRecord Structure

```python
class ToolCallRecord:
    call_id: str              # Unique identifier
    tool_id: str              # Which tool was called
    inputs: Dict              # What was passed in
    output: Any               # What the tool returned
    error: Optional[str]      # Error if tool failed
    started_at: str           # ISO timestamp
    completed_at: str         # ISO timestamp
```

### Example: Search Tool

```yaml
nodes:
  - id: "search"
    kind: "agent"
    tools: ["search_codebase"]
```

Execution:

```python
# Tool executes
output = {
    "result": "Found 3 files",
    "tool_calls": [
        {
            "call_id": "call-1",
            "tool_id": "search_codebase",
            "inputs": {"query": "authenticate", "path": "/src"},
            "output": [
                "src/auth.py",
                "src/login.py",
                "src/permissions.py"
            ]
        }
    ]
}

# Next node receives this in its context
# Can reference: tool_calls[0].output
```

---

## Linear Workflows

### Simple Sequential Flow

```
Input: "analyze this code"
  ↓
[START] → normalize input
  ↓
[SEARCH] → find related files
  ↓ (output: ["auth.py", "config.py"])
[READ] → read those files
  ↓ (output: {files: {...}})
[SUMMARIZE] → create summary
  ↓ (output: "summary: ...")
[EXIT] → end
```

### Example Workflow

```yaml
workflow:
  nodes:
    - id: "start"
      kind: "deterministic"
      role: "start"
      default_start: true
      context: "none"

    - id: "search_files"
      kind: "agent"
      role: "linear"
      agent_id: "searcher"
      tools: ["search_codebase"]
      context: "global"

    - id: "read_content"
      kind: "agent"
      role: "linear"
      agent_id: "reader"
      tools: ["read_file"]
      context: "global"    # Can see search results

    - id: "generate_analysis"
      kind: "agent"
      role: "linear"
      agent_id: "analyzer"
      tools: []
      context: "global"    # Can see search & read results

    - id: "exit"
      kind: "deterministic"
      role: "exit"
      context: "none"

  edges:
    - from: "start"
      to: "search_files"
    - from: "search_files"
      to: "read_content"
    - from: "read_content"
      to: "generate_analysis"
    - from: "generate_analysis"
      to: "exit"
```

### What Each Node Receives

```
START:
  Input: {request: "analyze auth module"}
  Output: {request: "analyze auth module"}  # Normalized

SEARCH_FILES:
  Input: {request: "analyze auth module"}
  Context: [previous tasks about auth, project docs, ...]
  Tools: search_codebase → finds ["auth.py", "login.py"]
  Output: {result: "...", tool_calls: [...]}

READ_CONTENT:
  Input: {result: "...", tool_calls: [...]}  ← SEARCH's output
  Context: [includes SEARCH results]
  Tools: read_file → reads auth.py and login.py
  Output: {files: {auth.py: "code...", login.py: "code..."}}

GENERATE_ANALYSIS:
  Input: {files: {...}}  ← READ's output
  Context: [includes SEARCH and READ results]
  No tools needed
  Output: "This module handles authentication with JWT..."

EXIT:
  Input: "This module handles authentication with JWT..."
  Output: Task complete
```

---

## Decision Routing

### Conditional Branching

Some workflows need to make decisions and branch:

```
                    ┌─ if "needs_creation"
                    │
[CLASSIFY] ────────┤─ if "needs_update"
                    │
                    └─ if "needs_deletion"
                    ↓ ↓ ↓
                  [A] [B] [C]
                    ↓ ↓ ↓
                    └─┴─┴─→ [FINALIZE]
```

### Decision Node Setup

```yaml
nodes:
  - id: "classify_request"
    kind: "agent"
    role: "decision"         # Key: role is "decision"
    agent_id: "classifier"
    context: "global"

  - id: "create_document"
    kind: "agent"
    role: "linear"
    agent_id: "creator"

  - id: "update_document"
    kind: "agent"
    role: "linear"
    agent_id: "updater"

  - id: "finalize"
    kind: "agent"
    role: "merge"           # Collects from multiple branches
    agent_id: "finalizer"

edges:
  - from: "classify_request"
    to: "create_document"
    label: "create"         # If output contains "create"

  - from: "classify_request"
    to: "update_document"
    label: "update"         # If output contains "update"

  - from: "create_document"
    to: "finalize"

  - from: "update_document"
    to: "finalize"
```

### How Routing Works

```
CLASSIFY outputs:
{
  "decision": "create",
  "reason": "User requested new document"
}

Engine examines output for routing label match:
  - Does output contain "create"? YES
  - Route to: create_document
  - Does output contain "update"? NO
  - Don't route there

Downstream node receives:
  Input = CLASSIFY's output
  Can see CLASSIFY's context & tool calls
```

### Merge Nodes

After branching, merge nodes collect results:

```yaml
nodes:
  - id: "finalize"
    kind: "agent"
    role: "merge"     # Special: can receive from multiple sources
```

```
          [CREATE] ──┐
                     ├─→ [MERGE] ← receives both outputs
          [UPDATE] ──┘

MERGE receives context containing:
- CREATE's output
- UPDATE's output
- All their tool calls
- Routing decision that was made
```

---

## Advanced Patterns

### Pattern 1: Gather & Process

Collect data from multiple sources, then analyze together:

```yaml
nodes:
  - id: "search_docs"
    kind: "agent"
    role: "split"      # Can output to multiple nodes
    tools: ["search_docs"]

  - id: "search_code"
    kind: "agent"
    role: "split"
    tools: ["search_code"]

  - id: "analyze_together"
    kind: "agent"
    role: "merge"      # Combines both searches
    context: "global"  # Can see both search results

edges:
  - from: "search_docs"
    to: "analyze_together"
  - from: "search_code"
    to: "analyze_together"
```

### Pattern 2: Iterative Refinement

Route back to previous node if output doesn't meet criteria:

```
[GENERATE] → [EVALUATE]
              ├─ if "good" → [EXIT]
              └─ if "poor" → [REFINE] → back to [GENERATE]
```

(Note: Requires careful DAG design to avoid infinite loops)

### Pattern 3: Context Accumulation

Store intermediate results in PROJECT memory for reuse:

```
[STEP 1] → Finds data → Save to PROJECT memory
   ↓
[STEP 2] → Sees STEP 1 data in context → Processes further
   ↓
[STEP 3] → Can reference both STEP 1 & 2 via context
```

Configure:

```yaml
nodes:
  - id: "step1"
    context: "global"     # Can access memory
  - id: "step2"
    context: "global"     # Sees step1's output in context
  - id: "step3"
    context: "global"     # Sees step1 & step2 outputs
```

---

## Debugging Data Flow

### Issue: Data Not Reaching Next Node

**Symptom:** Next node says it has no input

**Diagnosis:**
1. Check previous node's output is not None
2. Check current node has `context: "global"` (if it needs context)
3. Check edges in workflow.yaml connect the nodes

**Debug:**
```python
# After running workflow
task = engine.run({"request": "test"})

# Check each node's output
for record in task.history:
    print(f"{record.node_id}: {record.output}")
```

### Issue: Tools Not Being Found

**Symptom:** "Tool 'search_codebase' not found"

**Diagnosis:**
1. Tool defined in tools.yaml?
2. Tool ID matches workflow.yaml reference?
3. Entrypoint points to real function?

**Debug:**
```python
engine = Engine.from_config_dir("config")
print("Available tools:", engine.tools.keys())
```

### Issue: Context Not Available

**Symptom:** Agent says it can't see previous results

**Diagnosis:**
1. Check node has `context: "global"` or appropriate tier
2. Check previous nodes have executed
3. Check memory stores initialized

**Debug:**
```python
# Check context was assembled
print(engine.context_assembler.get_context(...))
```

### Visualization: Task Execution Timeline

```
Task execution with outputs:

Time │ Node          │ Input              │ Output
─────┼───────────────┼────────────────────┼──────────────────────
  1  │ START         │ {request: "find"}  │ {normalized: "find..."}
  2  │ SEARCH        │ {normalized: ...}  │ {files: ["a.py"]}
  3  │ READ          │ {files: [...]}     │ {content: "..."}
  4  │ ANALYZE       │ {content: "..."}   │ {summary: "..."}
  5  │ EXIT          │ {summary: "..."}   │ {done: true}
```

---

## FAQ

**Q: Can I access a tool's output in the next node?**
A: Yes! The tool output is part of the node's output, visible in context.

**Q: Can I skip context for a node?**
A: Yes, set `context: "none"` to exclude memory.

**Q: How much context can a node see?**
A: All items in its context tier, up to the configured token budget.

**Q: What if two nodes write conflicting data?**
A: They write to separate memory tiers (task vs project). Design your workflow to avoid conflicts.

**Q: Can I pass data between arbitrary nodes?**
A: Only through edges (sequential or via merge). Agent Engine enforces DAG structure.

---

## See Also

- [GETTING_STARTED.md](./GETTING_STARTED.md) - Configuration guide
- [ARCHITECTURE.md](./ARCHITECTURE.md) - DAG concepts and roles
- [API_REFERENCE.md](./API_REFERENCE.md) - Complete API documentation
