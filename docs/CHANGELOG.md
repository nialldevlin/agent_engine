# LLM NOTICE: Do not modify this file unless explicitly instructed by the user.

# Changelog

## 2025-12-11
- **Phases 19-23 Complete**: Final implementation phases for Agent Engine v1
  - Phase 19: Persistent Memory (40 tests) - Memory store persistence and recovery
  - Phase 20: Credentials & Secrets (43 tests) - Secure credential management
  - Phase 21: Scheduler (41 tests) - Task scheduling and delayed execution
  - Phase 22: Deployment Utilities (17 tests) - Production deployment helpers
  - Phase 23: Documentation & Examples (15 tests) - Example applications and usage guides
- **v1 Completion**: Agent Engine v1 fully implemented with 1,127 passing tests across all 24 phases
- **Documentation Cleanup**: Archived 8 completed phase implementation plans; reduced docs/ from 552 KB to ~310 KB

## 2025-12-05
- **Phase 3 Complete:** Implemented DAG-based workflow engine with full specification.
  - Phase 3.1: Added `StageRole` enum and `role` field to `Stage`; enhanced `Edge` and `WorkflowGraph` schemas with optional fields.
  - Phase 3.2: Implemented pure `validate_workflow_graph(...)` function for DAG validation (cycle detection, reachability, edge validation).
  - Phase 3.3: Implemented `stage_library.py` with four stage runner functions (`run_agent_stage`, `run_tool_stage`, `run_decision_stage`, `run_merge_stage`); fixed `PipelineExecutor` structural issues and restored all instance methods.
  - Phase 3.4: Added `Router.resolve_edge(...)` for deterministic decision routing; injected checkpoint saving via `TaskManager.save_checkpoint(...)` and enhanced telemetry events (`stage_started`, `stage_finished`, `checkpoint_error`).
  - Phase 3.5: Added comprehensive DAG execution tests demonstrating decision-based routing and merge stage aggregation.
  - Closed operational `PHASE_3_IMPLEMENTATION_BRIEF.md` into this changelog; all 10 tests passing (runtime, validators, DAG execution).

## 2025-12-06
- **Phase 0 Complete:** Engine façade now includes manifest loading, public API exports, and `register_tool_handler` (Step 8) so applications can plug in deterministic tools while the runtime stays encapsulated; README/plan docs were refreshed to describe the stable API, helper-based example tests continue to exercise Engine usage, and the `basic_llm_agent` CLI example was removed pending a future canonical version.

## 2025-12-04
- Repository: closed out operational Phase 0–2 artifacts and consolidated active plans.
- Deleted redundant operational plan and phase documents to reduce maintenance and surface current plan (`PLAN_BUILD_AGENT_ENGINE.md` now acts as master with phases closed through Phase 2).
- Verified and committed Task persistence work (checkpointing, load, list, metadata) and added VS Code workspace settings; full test suite passing (360 tests).

## 2025-12-03
- Added documentation rules and cleaned obsolete operational archives to reduce maintenance overhead.
- Captured King Arthur integration planning guidance in `legacy/king_arthur/INTEGRATION_PLAN.md` and pointed Sonnet plan at it.
- Cleaned canonical and operational docs (standardized headings, updated plan summaries, referenced doc rules).

- Closed PLAN_CODEX after completion (see repo history for details) and removed outdated GETTING_STARTED and architecture pointer docs to prevent stale guidance.
- Replaced legacy knight roles with neutral agent manifests, removed ContextStore fallback, and quarantined the King Arthur lift under `legacy/king_arthur/`.
