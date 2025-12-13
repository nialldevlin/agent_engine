# Agent Engine Fix Plan

Status: draft  
Source of truth: docs/canonical/AGENT_ENGINE_OVERVIEW.md

## Goals
- Bring runtime semantics, validation, and observability into full alignment with the canonical overview.
- Close execution gaps around routing, memory/context, schema enforcement, tool usage, status propagation, and multi-task scheduling.
- Keep backwards compatibility for examples and tests while enforcing stricter correctness where required.

## Workstream 1: Routing, Status, and History
- Fix branch/split/merge semantics: merges wait for required children, resume using parent task IDs, include success + failure metadata, and honor `merge_failure_mode`.
- Correct exit handling and lifecycle: set lifecycle to ACTIVE at start, conclude at exit, map statuses to `success/failure/partial` before return, remove invalid TaskLifecycle values.
- Record StageExecutionRecords in both ordered `history` and indexed `stage_results`; ensure task status is set before exit and propagate node/tool failures consistently.

## Workstream 2: Memory and Context
- Pass initialized task/project/global memory stores into ContextAssembler; stop creating ad-hoc in-memory stores.
- Write key artifacts into memory (reasoning, tool outputs, node outputs as appropriate) so downstream nodes receive deterministic context per profile.
- Ensure context profiles resolve from manifests and enforce retrieval policies; emit context metadata to telemetry.

## Workstream 3: Schema Enforcement
- Register schemas from `config_dir/schemas/*.json` into the JSON engine at init time.
- Validate node inputs/outputs and tool I/O against project-defined schemas; fail fast on unknown schema IDs with clear errors.

## Workstream 4: Tools and Policies
- Allow deterministic nodes with `tools` to invoke ToolRuntime (with same permission/policy checks as agents).
- Apply security/policy checks uniformly to all tool calls; include filesystem/network/root scopes based on manifest + workspace_root.
- Ensure tool calls are captured in StageExecutionRecords, artifacts, and telemetry.

## Workstream 5: DAG Validation and Scheduler
- Update DAG validation to permit disconnected components (each with start + exit) while keeping role/edge constraints.
- Improve scheduler to support configurable concurrency (cooperative), consistent task states, and integration with router execution.
- Ensure queue/inspector surfaces per-task history/artifacts accurately in multi-task mode.

## Workstream 6: Merge Payload Fidelity
- Build merge payloads with lineage metadata, node IDs, outputs, statuses, and failure info for diagnostic selection.
- Respect `merge_failure_mode` to set parent status (fail_on_any, ignore_failures, partial) before routing continues.

## Workstream 7: Telemetry and Artifacts
- Emit telemetry with normalized status/lifecycle and engine metadata; include routing decisions, tool/context events.
- Store node outputs and tool results in ArtifactStore with schema refs when present; ensure inspector can retrieve.

## Workstream 8: Tests and Examples
- Add/adjust tests for routing (branch/split/merge), deterministic tool usage, schema loading, memory/context assembly, multi-task scheduling, and DAG validation rules.
- Re-run examples (`minimal_config`, `mini_editor`) to confirm end-to-end behavior under corrected semantics.

## Guardrails
- Do not modify docs/canonical/AGENT_ENGINE_OVERVIEW.md.
- Preserve existing user changes; only tighten behavior where it matches the canonical overview.
