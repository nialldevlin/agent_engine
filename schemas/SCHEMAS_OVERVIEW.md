# SCHEMAS_OVERVIEW.md

Contracts and data model blueprint for Agent Engine. These are language‑agnostic, JSON‑shaped definitions to guide implementation and manifest validation. They align with `AGENT_ENGINE_OVERVIEW.md` and `RESEARCH_UPDATED.md`. No runtime code is included in this phase.

## Modeling Notes

- Favor explicit IDs, version fields, and schema IDs to support validation and evolution.
- Keep required fields minimal; use optional/nullable fields for forward compatibility.
- Timestamps are ISO‑8601 strings; enums are lowercase strings.
- References between entities use stable IDs (e.g., `task_id`, `stage_id`, `agent_id`, `tool_id`, `pipeline_id`).

## TaskSpec (normalized user request)

```json
{
  "task_spec_id": "string",
  "request": "string",               // raw or normalized user ask
  "mode": "enum: analysis_only | implement | review | dry_run",
  "priority": "enum: low | normal | high",
  "hints": ["string"],               // optional user hints or file pointers
  "files": ["string"],               // optional explicit file paths
  "overrides": ["override_id"],      // links to OverrideSpec objects
  "metadata": { "string": "any" }
}
```

## Task

```json
{
  "task_id": "string",
  "spec": "TaskSpec",
  "status": "enum: pending | running | completed | failed",
  "pipeline_id": "string",
  "current_stage_id": "string | null",
  "stage_results": {
    "stage_id": {
      "output": "any",
      "error": "EngineError | null",
      "started_at": "timestamp",
      "completed_at": "timestamp"
    }
  },
  "routing_trace": [
    { "stage_id": "string", "decision": "string", "agent_id": "string | null", "timestamp": "timestamp" }
  ],
  "failure_signatures": ["FailureSignature"],
  "context_fingerprint": "ContextFingerprint | null",
  "created_at": "timestamp",
  "updated_at": "timestamp"
}
```

## FailureSignature

```json
{
  "code": "enum: plan_invalid | tool_failure | json_error | context_miss | timeout | unknown",
  "message": "string",
  "stage_id": "string | null",
  "severity": "enum: info | warning | error",
  "metadata": { "string": "any" }
}
```

## Stage

```json
{
  "stage_id": "string",
  "name": "string",
  "type": "enum: agent | tool | decision | merge | transform",
  "entrypoint": "bool",                 // start node
  "terminal": "bool",                   // end node
  "agent_id": "string | null",          // for agent stages
  "tool_id": "string | null",           // for tool stages
  "inputs_schema_id": "string | null",  // schema to validate stage input
  "outputs_schema_id": "string | null", // schema to validate stage output
  "on_error": {
    "policy": "enum: fail | retry | skip | fallback_stage",
    "max_retries": "int | null",
    "fallback_stage_id": "string | null"
  },
  "metadata": { "string": "any" }
}
```

## WorkflowGraph

```json
{
  "workflow_id": "string",
  "stages": ["Stage"],
  "edges": [
    {
      "from_stage_id": "string",
      "to_stage_id": "string",
      "condition": "string | null"   // tag or expression for decision routing
    }
  ],
  "invariants": {
    "acyclic": true,
    "reachable_end_from_start": true
  }
}
```

## Pipeline

```json
{
  "pipeline_id": "string",
  "name": "string",
  "description": "string",
  "workflow_id": "string",
  "start_stage_ids": ["string"],
  "end_stage_ids": ["string"],
  "allowed_modes": ["analysis_only | implement | review | dry_run"],
  "fallback_end_stage_ids": ["string"],      // optional degraded/abort paths
  "metadata": { "string": "any" }
}
```

## AgentDefinition

```json
{
  "agent_id": "string",
  "role": "enum: agent",
  "profile": {
    "specialty": ["string"],                 // domains/files/tags
    "risk_tolerance": "enum: low | medium | high",
    "capabilities": ["string"],              // tools, planning depth, etc.
    "templates": { "mode": "template_id" }   // prompt template references
  },
  "manifest": {
    "reasoning_steps": "int | null",
    "tool_bias": "enum: prefer_tools | prefer_text | balanced",
    "verbosity": "enum: terse | normal | verbose",
    "tests_emphasis": "enum: low | medium | high"
  },
  "schema_id": "string",                     // expected agent output schema
  "version": "string",
  "metadata": { "string": "any" }
}
```

## ToolDefinition

```json
{
  "tool_id": "string",
  "kind": "enum: deterministic | llm_tool",
  "name": "string",
  "description": "string",
  "inputs_schema_id": "string",
  "outputs_schema_id": "string",
  "capabilities": ["enum: deterministic_safe | workspace_mutation | external_network | expensive"],
  "allowed_context": ["string"],         // e.g., files, domains, tags
  "risk_level": "enum: low | medium | high",
  "version": "string",
  "metadata": { "string": "any" }
}
```

## ToolPlan and ToolCallRecord

```json
{
  "tool_plan_id": "string",
  "steps": [
    {
      "step_id": "string",
      "tool_id": "string",
      "inputs": "any",
      "reason": "string",
      "kind": "enum: read | write | analyze | test"
    }
  ]
}
```

```json
{
  "call_id": "string",
  "tool_id": "string",
  "stage_id": "string",
  "inputs": "any",
  "output": "any",
  "error": "EngineError | null",
  "started_at": "timestamp",
  "completed_at": "timestamp",
  "metadata": { "string": "any" }
}
```

## MemoryConfig and Context Items

```json
{
  "memory_config_id": "string",
  "stores": {
    "task": { "retention": "string", "max_items": "int" },
    "project": { "retention": "string", "max_items": "int" },
    "global": { "retention": "string", "max_items": "int" }
  },
  "compression_policy": {
    "mode": "enum: cheap | balanced | max_quality",
    "compression_ratio_target": "number"
  },
  "context_policy": {
    "head_tail_preserve": "int",     // number of most recent turns to keep
    "middle_compress": true
  },
  "metadata": { "string": "any" }
}
```

### ContextItem

```json
{
  "context_item_id": "string",
  "kind": "enum: task | project | global",
  "source": "string",                   // file path, agent id, tool id, user
  "timestamp": "timestamp",
  "tags": ["string"],
  "importance": "number",               // heuristic or learned score
  "token_cost": "number",
  "payload": "string | object",
  "metadata": { "string": "any" }
}
```

### ContextFingerprint

```json
{
  "task_id": "string",
  "files": ["string"],
  "tags": ["string"],
  "mode": "string",
  "approx_complexity": "number",
  "hash": "string"                      // stable hash for telemetry/routing
}
```

### ContextRequest / ContextPackage

```json
{
  "context_request_id": "string",
  "budget_tokens": "int",
  "domains": ["string"],                // e.g., code, tests, docs, chat_history
  "history_types": ["string"],          // e.g., turns, summaries, decisions
  "mode": "string",
  "agent_profile": "string"             // agent_id or profile id
}
```

```json
{
  "context_package_id": "string",
  "items": ["ContextItem"],
  "summary": "string | null",
  "compression_ratio": "number | null"
}
```

## Event

```json
{
  "event_id": "string",
  "task_id": "string | null",
  "stage_id": "string | null",
  "type": "enum: task | stage | agent | tool | routing | memory | error | telemetry",
  "timestamp": "timestamp",
  "payload": "object",
  "metadata": { "string": "any" }
}
```

## OverrideSpec

```json
{
  "override_id": "string",
  "kind": "enum: memory | routing | safety | verbosity | mode",
  "scope": "enum: task | project | global",
  "target": "string | null",            // e.g., agent_id, tool_id, memory store
  "severity": "enum: hint | enforce",
  "payload": "object",
  "metadata": { "string": "any" }
}
```

## EngineError

```json
{
  "error_id": "string",
  "code": "enum: validation | routing | tool | agent | json | security | unknown",
  "message": "string",
  "source": "enum: config_loader | runtime | agent_runtime | tool_runtime | json_engine | memory | router",
  "severity": "enum: info | warning | error | critical",
  "details": "object | null",
  "stage_id": "string | null",
  "task_id": "string | null",
  "timestamp": "timestamp"
}
```

## Rationale Summary

- **Task/TaskSpec** separate immutable intent from mutable execution state, enabling reproducibility and clean routing decisions.
- **Stage/WorkflowGraph/Pipeline** encode DAG structure with explicit entry/terminal semantics to enforce termination and validate manifests statically.
- **Agent/Tool** definitions carry role, capabilities, risk, and schema IDs to support routing, safety checks, and structured IO.
- **Memory/Context** models expose multi-tier storage with metadata to enable paging, compression, and debugging of context assembly.
- **Event/Override/FailureSignature/EngineError** provide structured observability, user control, and recovery hooks consistent with the research guidance on telemetry and fallback behaviors.
